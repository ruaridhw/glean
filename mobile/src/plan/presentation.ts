import { isExpiringSoon } from "@/pantry/presentation";
import type { MealPlanEntry, PantryItem } from "@/types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

interface PlanProgress {
  label: string;
  percent: number;
}

export interface PlanSlot {
  key: string;
  slotNumber: number;
  entry: MealPlanEntry | null;
}

export function formatPlanProgress(planned: number, target: number): PlanProgress {
  return {
    label: `${planned} of ${target} dinners`,
    percent: target > 0 ? Math.min((planned / target) * 100, 100) : 0,
  };
}

export function getPlanSubtitle(entries: MealPlanEntry[], target: number): string {
  return formatPlanProgress(entries.length, target).label;
}

export function buildPlanSlots(entries: MealPlanEntry[], target: number): PlanSlot[] {
  const entrySlots = entries.map((entry, index) => ({
    key: `entry-${entry.id}`,
    slotNumber: index + 1,
    entry,
  }));
  const emptyCount = Math.max(0, target - entries.length);
  return [
    ...entrySlots,
    ...Array.from({ length: emptyCount }, (_, index) => ({
      key: `empty-${index + 1}`,
      slotNumber: entries.length + index + 1,
      entry: null,
    })),
  ];
}

export function getCurrentWeekRangeLabel(now: Date = new Date()): string {
  const start = new Date(now);
  const day = start.getDay();
  const mondayOffset = day === 0 ? -6 : 1 - day;
  start.setDate(start.getDate() + mondayOffset);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  if (start.getMonth() === end.getMonth()) {
    return `${start.getDate()}–${end.getDate()} ${MONTHS[start.getMonth()]}`;
  }
  return `${start.getDate()} ${MONTHS[start.getMonth()]} – ${end.getDate()} ${MONTHS[end.getMonth()]}`;
}

/** Geometry + arc math for the 56px SVG dinner-progress ring. */
interface PlanRingModel {
  size: number;
  radius: number;
  strokeWidth: number;
  center: number;
  circumference: number;
  /** `stroke-dasharray` value: "<filled> <circumference>". */
  dashArray: string;
  ratioLabel: string;
}

const RING_SIZE = 56;
const RING_STROKE = 6;
const RING_RADIUS = 24;

export function getPlanRingModel(planned: number, target: number): PlanRingModel {
  const circumference = 2 * Math.PI * RING_RADIUS;
  const fraction = target > 0 ? Math.min(Math.max(planned / target, 0), 1) : 0;
  const filled = fraction * circumference;
  return {
    size: RING_SIZE,
    radius: RING_RADIUS,
    strokeWidth: RING_STROKE,
    center: RING_SIZE / 2,
    circumference,
    dashArray: `${filled} ${circumference}`,
    ratioLabel: `${planned}/${target}`,
  };
}

export function getPlanHint(planned: number, target: number): string {
  const remaining = target - planned;
  if (remaining <= 0) return "Week fully planned — nice";
  return `${remaining} dinner${remaining === 1 ? "" : "s"} left to plan this week`;
}

/**
 * Nudge about soon-to-expire pantry items, surfaced on the Plan screen so users
 * plan a dinner that uses them up. Derived from `isExpiringSoon` (pantry
 * presentation) over the pantry rows loaded alongside the plan — an item counts
 * as urgent when it is expired or within the "soon" window (≤2 days).
 * Returns null when nothing is expiring so the banner hides gracefully.
 */
export interface PlanExpiryNudge {
  count: number;
  title: string;
  message: string;
}

export function getPlanExpiryNudge(
  items: PantryItem[],
  now: Date = new Date(),
): PlanExpiryNudge | null {
  const urgent = items.filter((item) => isExpiringSoon(item, now));
  if (urgent.length === 0) return null;

  const names = urgent.map((item) => item.canonical_name);
  const preview =
    names.length <= 2
      ? names.join(" and ")
      : `${names.slice(0, 2).join(", ")} and ${names.length - 2} more`;
  const single = urgent.length === 1;
  return {
    count: urgent.length,
    title: single ? "1 item needs using up" : `${urgent.length} items need using up`,
    message: `${preview} ${single ? "is" : "are"} expiring soon — plan a dinner to use ${
      single ? "it" : "them"
    } up.`,
  };
}
