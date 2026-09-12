/**
 * 슬롯 아이콘 (키트 제공) — kind에 맞는 아이콘을 골라 줍니다.
 * 새로운 kind를 쓰면 기본 아이콘이 나오므로, 화면이 깨지지 않습니다.
 */
"use client";

import {
  Activity,
  BarChart3,
  Camera,
  Cog,
  Droplet,
  Gauge,
  Hand,
  Lightbulb,
  Palette,
  Power,
  Radio,
  Rotate3d,
  Ruler,
  Sun,
  Thermometer,
  User,
  Volume2,
} from "lucide-react";
import React from "react";

import { Slot, iconNameFor } from "@/lib/slots";

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  volume: Volume2,
  lightbulb: Lightbulb,
  power: Power,
  rotate: Rotate3d,
  palette: Palette,
  vibrate: Radio,
  cog: Cog,
  bars: BarChart3,
  hand: Hand,
  user: User,
  activity: Activity,
  thermometer: Thermometer,
  droplet: Droplet,
  ruler: Ruler,
  gauge: Gauge,
  sun: Sun,
  camera: Camera,
};

export default function SlotIcon({
  slot,
  className = "w-4 h-4",
}: {
  slot: Slot;
  className?: string;
}) {
  const Icon = ICONS[iconNameFor(slot)] ?? Activity;
  return <Icon className={className} />;
}
