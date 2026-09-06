# ==============================================================================
# 스마트 기상 시스템 - 1차 완성형 Windows 통합 실행 런처 (PowerShell)
# ==============================================================================
# 1. 백엔드 (FastAPI + MariaDB/Mock)
# 2. 프론트엔드 (Next.js 실시간 대시보드)
# 3. 하드웨어 Mock-up (라즈베리파이 5 시뮬레이터 GUI + 부저 비프음)
# 4. 영상인식 클라이언트 (YOLOv8 웹캠 기상 미션)
# ==============================================================================

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " [스마트 기상 시스템 - 1차 완성형 Windows 통합 실행기]" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " 1. 백엔드 서버      : http://localhost:8000 (Swagger: /docs)" -ForegroundColor Gray
Write-Host " 2. 프론트엔드 대시보드: http://localhost:3000" -ForegroundColor Gray
Write-Host " 3. 하드웨어 Mock-up  : 윈도우 사운드 비프 + GUI 터치패드 창" -ForegroundColor Gray
Write-Host " 4. 웹캠 비전 클라이언트: YOLOv8 기상 미션 객체 감지 창" -ForegroundColor Gray
Write-Host "-----------------------------------------------------------------" -ForegroundColor Cyan

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. 백엔드 실행 창
Write-Host ">> [1/4] 백엔드(FastAPI) 서버 창을 엽니다..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\backend'; .\venv\Scripts\Activate.ps1; Write-Host '--- [1] 백엔드 FastAPI 서버 실행 중 ---' -ForegroundColor Green; uvicorn main:app --reload --host 0.0.0.0 --port 8000"

Start-Sleep -Seconds 2

# 2. 프론트엔드 실행 창
Write-Host ">> [2/4] 프론트엔드(Next.js) 대시보드 창을 엽니다..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\frontend'; Write-Host '--- [2] 프론트엔드 Next.js 대시보드 실행 중 ---' -ForegroundColor Green; npm run dev"

Start-Sleep -Seconds 2

# 3. 하드웨어 Mock-up 실행 창
Write-Host ">> [3/4] 하드웨어(라즈베리파이 5) Mock-up 창을 엽니다..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\pi'; Write-Host '--- [3] 하드웨어 Mock-up 시뮬레이터 실행 중 ---' -ForegroundColor Green; python main.py"

Start-Sleep -Seconds 1

# 4. 영상인식 웹캠 클라이언트 실행 창
Write-Host ">> [4/4] 영상인식(YOLOv8) 웹캠 클라이언트 창을 엽니다..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\vision'; .\venv\Scripts\Activate.ps1; Write-Host '--- [4] YOLOv8 웹캠 비전 클라이언트 실행 중 ---' -ForegroundColor Green; python main.py"

Write-Host "-----------------------------------------------------------------" -ForegroundColor Cyan
Write-Host " 4개 컴포넌트가 모두 별도 터미널 창에서 정상 구동되었습니다!" -ForegroundColor Yellow
Write-Host " 브라우저에서 http://localhost:3000 으로 접속해 확인하세요." -ForegroundColor Yellow
Write-Host "=================================================================" -ForegroundColor Cyan
