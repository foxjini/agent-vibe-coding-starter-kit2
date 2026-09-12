"""
플랫폼 키트 API — 슬롯 레지스트리 · 배치 통신 · 자동화 규칙
(docs/부록F-IoT-개발-플랫폼-키트-규약.md 5·7장)

이 라우터는 **부품의 의미를 모릅니다**. 슬롯 ID와 메타데이터만 다루므로
팀이 센서·액추에이터를 바꿔도 이 파일은 수정하지 않습니다.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import verify_device_api_key, verify_user_auth
from db.database import (
    ACTUATOR_SLOTS,
    SENSOR_SLOTS,
    create_rule,
    delete_rule,
    get_db_status,
    get_rule,
    get_slots,
    list_rules,
    register_slots,
    slot_role,
    update_rule,
    update_slot_metadata,
)
from schemas.common import DataResponse
from schemas.slot import (
    RuleUpsertRequest,
    SlotMetadataUpdate,
    SlotRegisterRequest,
    StateReportRequest,
    TimerRequest,
)
from iot.provider_factory import get_device_provider
from services.rule_engine import rule_engine, validate_action, validate_definition
from services.slot_service import apply_state_reports, build_desired_states
from websocket_manager import ws_manager

logger = logging.getLogger("backend.routers.slots")

router = APIRouter(tags=["Platform Kit"])


def _not_a_slot(slot_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": {
                "code": "INVALID_SLOT_ID",
                "message": (
                    f"'{slot_id}'는 플랫폼 슬롯이 아닙니다. "
                    f"sensor_01~sensor_{len(SENSOR_SLOTS):02d} 또는 "
                    f"actuator_01~actuator_{len(ACTUATOR_SLOTS):02d} 중에서 지정하세요."
                ),
            }
        },
    )


def _db_required() -> HTTPException:
    """규칙은 DB에만 저장되므로, DB가 꺼져 있으면 솔직하게 503으로 알려 준다."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": {
                "code": "DB_UNAVAILABLE",
                "message": (
                    "데이터베이스에 연결되지 않아 자동화 규칙을 저장할 수 없습니다. "
                    "MySQL/MariaDB를 켜고 다시 시도하세요 (상태는 GET /health)."
                ),
            }
        },
    )


# ==============================================================================
# 슬롯 레지스트리 (대시보드)
# ==============================================================================

@router.get(
    "/api/slots",
    response_model=DataResponse[List[Dict[str, Any]]],
    summary="[키트] 슬롯 20개 목록 조회 (하드웨어 구성 화면용)",
)
async def list_slots(
    role: Optional[str] = Query(None, pattern="^(sensor|actuator)$"),
    enabled_only: bool = Query(False, description="팀이 실제로 쓰는 슬롯만"),
    user=Depends(verify_user_auth),
):
    """
    센서·액추에이터 슬롯 목록과 메타데이터를 돌려줍니다.
    빈 슬롯까지 모두 보여주므로 '하드웨어 구성' 설정 화면에서 그대로 표로 쓸 수 있습니다.
    """
    slots = await asyncio.to_thread(get_slots, role, enabled_only)
    if not slots:
        # DB가 꺼져 있어도 하드웨어 구성 화면이 비어 보이지 않게 메모리 캐시로 폴백한다
        slots = get_device_provider().cached_slots(role, enabled_only)
    for slot in slots:
        slot["slot_id"] = slot.get("id")
    return {"data": slots}


@router.patch(
    "/api/slots/{slot_id}",
    response_model=DataResponse[Dict[str, Any]],
    summary="[키트] 슬롯 메타데이터 수정 (라벨·종류·사용여부)",
)
async def patch_slot(
    slot_id: str,
    payload: SlotMetadataUpdate,
    user=Depends(verify_user_auth),
):
    """
    슬롯에 '의미'를 부여합니다 — 코드가 아니라 데이터를 바꾸는 작업입니다.
    부품을 떼려면 `enabled: false`로 두세요(슬롯 자체는 삭제하지 않습니다).
    role·slot_index는 불변이므로 수정할 수 없습니다.
    """
    if slot_role(slot_id) is None:
        raise _not_a_slot(slot_id)

    fields = payload.model_dump(exclude_unset=True, exclude_none=False)
    fields = {k: v for k, v in fields.items() if v is not None}
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "NOTHING_TO_UPDATE", "message": "수정할 항목이 없습니다."}},
        )

    provider = get_device_provider()
    await asyncio.to_thread(update_slot_metadata, slot_id, fields)
    # DB가 꺼져 있어도 그 세션 동안 동작하도록 메모리 캐시에도 반영한다
    provider.update_cached_metadata(slot_id, fields)

    slots = await asyncio.to_thread(get_slots, None, False)
    if not slots:
        slots = provider.cached_slots()
    updated = next((s for s in slots if s.get("id") == slot_id), None)
    if updated:
        updated["slot_id"] = updated.get("id")
        await ws_manager.broadcast({"type": "slot_config", **{
            k: updated.get(k) for k in
            ("slot_id", "role", "enabled", "label", "kind", "unit", "control_type", "display_order")
        }})
    return {"data": updated or {"slot_id": slot_id, **fields}}


# ==============================================================================
# 하드웨어 배치 통신 (라즈베리파이)
# ==============================================================================

@router.get(
    "/api/v1/devices/desired-states",
    response_model=DataResponse[Dict[str, Any]],
    summary="[하드웨어] 활성 액추에이터 목표 상태 일괄 조회",
)
async def get_desired_states(device_key=Depends(verify_device_api_key)):
    """
    라즈베리파이가 1초 주기로 호출하는 **단 하나의 폴링 엔드포인트**입니다.
    슬롯 20개를 개별 폴링하면 초당 20요청이 되므로 한 번에 묶어서 돌려줍니다.
    """
    return {"data": await build_desired_states()}


@router.post(
    "/api/v1/devices/states",
    response_model=DataResponse[Dict[str, Any]],
    summary="[하드웨어] 반영 상태·센서값 일괄 보고",
)
async def post_states(
    payload: StateReportRequest,
    device_key=Depends(verify_device_api_key),
):
    """
    액추에이터 반영 결과(state)와 센서 측정값(value)을 한 번에 보고합니다.
    항목 하나가 잘못되어도 나머지는 정상 처리하고, 거부된 것만 이유와 함께 돌려줍니다.
    """
    reports = [r.model_dump() for r in payload.states]
    accepted, rejected = await apply_state_reports(reports, payload.reported_at)
    return {"data": {"accepted": len(accepted), "accepted_slots": accepted, "rejected": rejected}}


@router.post(
    "/api/v1/devices/register",
    response_model=DataResponse[Dict[str, Any]],
    summary="[하드웨어] 슬롯 매핑 일괄 등록 (부팅 시 1회)",
)
async def post_register(
    payload: SlotRegisterRequest,
    device_key=Depends(verify_device_api_key),
):
    """
    라즈베리파이가 `pi/slot_map.py`의 내용을 그대로 올립니다.
    `exclusive`가 true면 목록에 없는 슬롯은 자동으로 비활성화되므로,
    **pi에서 한 줄을 지우면 대시보드에서도 사라집니다.**
    """
    slots = [s.model_dump(exclude_unset=True) for s in payload.slots]
    result = await asyncio.to_thread(register_slots, slots, payload.exclusive)
    # DB가 꺼져 있어도 그 세션 동안 동작하도록 메모리 캐시에도 반영한다
    cached = get_device_provider().apply_slot_registration(slots, payload.exclusive)
    if not result.get("registered") and not result.get("rejected"):
        # DB 장애로 아무것도 기록되지 않았다 → 캐시에 실제로 반영된 내용을 알려준다
        result = {**cached, "persisted": False}

    await ws_manager.broadcast({
        "type": "slot_config",
        "registered": result.get("registered", []),
        "disabled": result.get("disabled", []),
    })
    logger.info(
        f"[슬롯 등록] 활성 {len(result.get('registered', []))}개, "
        f"자동 비활성 {len(result.get('disabled', []))}개, "
        f"거부 {len(result.get('rejected', []))}개"
    )
    return {"data": result}


# ==============================================================================
# 자동화 규칙 (대시보드)
# ==============================================================================

@router.get(
    "/api/rules",
    response_model=DataResponse[List[Dict[str, Any]]],
    summary="[키트] 자동화 규칙 목록",
)
async def get_rules(
    enabled_only: bool = Query(False),
    user=Depends(verify_user_auth),
):
    return {"data": await asyncio.to_thread(list_rules, enabled_only)}


@router.post(
    "/api/rules",
    response_model=DataResponse[Dict[str, Any]],
    summary="[키트] 자동화 규칙 생성",
)
async def post_rule(payload: RuleUpsertRequest, user=Depends(verify_user_auth)):
    error = validate_definition(payload.definition)
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_RULE", "message": error}},
        )
    rule_id = await asyncio.to_thread(
        create_rule, payload.name, payload.definition, payload.enabled, payload.priority
    )
    if rule_id is None:
        raise _db_required()
    rule_engine.reset_state()
    return {"data": {"id": rule_id, "name": payload.name}}


@router.put(
    "/api/rules/{rule_id}",
    response_model=DataResponse[Dict[str, Any]],
    summary="[키트] 자동화 규칙 수정",
)
async def put_rule(rule_id: int, payload: RuleUpsertRequest, user=Depends(verify_user_auth)):
    error = validate_definition(payload.definition)
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_RULE", "message": error}},
        )
    if not await asyncio.to_thread(get_rule, rule_id):
        if not get_db_status()["connected"]:
            raise _db_required()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "RULE_NOT_FOUND", "message": f"규칙 #{rule_id}이 없습니다."}},
        )
    await asyncio.to_thread(update_rule, rule_id, {
        "name": payload.name,
        "definition": payload.definition,
        "enabled": payload.enabled,
        "priority": payload.priority,
    })
    rule_engine.reset_state()
    return {"data": {"id": rule_id, "updated": True}}


@router.delete(
    "/api/rules/{rule_id}",
    response_model=DataResponse[Dict[str, Any]],
    summary="[키트] 자동화 규칙 삭제",
)
async def remove_rule(rule_id: int, user=Depends(verify_user_auth)):
    deleted = await asyncio.to_thread(delete_rule, rule_id)
    if not deleted:
        if not get_db_status()["connected"]:
            raise _db_required()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "RULE_NOT_FOUND", "message": f"규칙 #{rule_id}이 없습니다."}},
        )
    rule_engine.reset_state()
    return {"data": {"id": rule_id, "deleted": True}}


# ==============================================================================
# 일회성 타이머 (시나리오 SDK의 serverTimer)
# ==============================================================================

@router.post(
    "/api/timers",
    response_model=DataResponse[Dict[str, Any]],
    summary="[키트] N초 뒤에 액션 하나를 한 번 실행",
)
async def post_timer(payload: TimerRequest, user=Depends(verify_user_auth)):
    """
    프론트엔드 시나리오는 브라우저 탭을 닫으면 멈춥니다. "미션 성공 60초 뒤 기상 확인"처럼
    **화면 없이도 일어나야 하는 동작**을 백엔드에 맡길 때 씁니다 (부록F 9-3절).

    규칙과 달리 저장되지 않으므로 서버를 재시작하면 사라집니다.
    반복되는 자동화는 타이머가 아니라 규칙(`/api/rules`)으로 만드세요.
    """
    error = validate_action(payload.action)
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_ACTION", "message": error}},
        )

    label = payload.label or "시나리오 타이머"
    rule_engine.schedule_once(payload.seconds, payload.action, label)
    return {"data": {"scheduled": True, "seconds": payload.seconds, "label": label}}
