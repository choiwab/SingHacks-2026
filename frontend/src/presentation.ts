import type { RankedClient } from "./contracts";

/** Attention state shown next to each client in the switcher. */
export const URGENCY: Record<
  RankedClient["urgency"],
  { label: string; color: "danger" | "warning" | "informative" }
> = {
  now: { label: "Act now", color: "danger" },
  soon: { label: "Prepare", color: "warning" },
  watch: { label: "Watch", color: "informative" },
};

export const NARROW = "@media (max-width: 60rem)";

export function formatValue(value: unknown) {
  if (value === null || value === undefined) return "Not recorded";
  if (typeof value === "number")
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return String(value);
}
