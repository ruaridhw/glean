import type { MealPlanEntry } from "@/types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export interface PlanProgress {
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
    return `${start.getDate()}-${end.getDate()} ${MONTHS[start.getMonth()]}`;
  }
  return `${start.getDate()} ${MONTHS[start.getMonth()]} - ${end.getDate()} ${MONTHS[end.getMonth()]}`;
}
