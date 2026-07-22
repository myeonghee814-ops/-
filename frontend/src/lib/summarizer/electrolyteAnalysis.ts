/**
 * Best-effort derivation of structured electrolyte-composition/performance
 * signals from PaperSummary's free-text fields (dashboardComponents,
 * experimentalPerformance). None of these require an extra Gemini call -
 * they only re-derive what's already been extracted, so both the "전체
 * 분석" dashboard (OverallAnalysisView) and the AI trend-insight prompt
 * (gemini.ts's getTrendInsight) can share the exact same interpretation of
 * a paper's data instead of drifting apart.
 */
import type { AdditiveOrCosolvent, ExperimentalPerformanceEntry } from "../../types/summarizer";

export const NO_INFO = "정보 없음";

/** Gemini's extraction prompt documents electrolyte_base in the shape
 * "<molarity> <salt> in <solvent>" (e.g. "1.2M LiPF6 in EC/EMC") - split on
 * " in " to recover salt/solvent as separate values. This is a
 * best-effort text split, not a real chemistry parser: if a paper's value
 * doesn't follow that shape, the whole string goes into `salt` and
 * `solvent` falls back to "정보 없음" rather than guessing wrong. */
export function splitElectrolyteBase(base: string): { solvent: string; salt: string } {
  if (!base || base === NO_INFO) return { solvent: NO_INFO, salt: NO_INFO };
  const match = base.match(/^(.+?)\s+in\s+(.+)$/i);
  if (!match) return { solvent: NO_INFO, salt: base };
  const [, salt, solvent] = match;
  return { solvent: solvent.trim(), salt: salt.trim() };
}

/** "FEC (5wt%), VC (2wt%)" - omits the ratio when it's itself "정보 없음" so
 * the result doesn't read "FEC (정보 없음)". */
export function formatAdditives(additives: AdditiveOrCosolvent[]): string {
  if (additives.length === 0) return NO_INFO;
  return additives.map((a) => (a.ratio && a.ratio !== NO_INFO ? `${a.name} (${a.ratio})` : a.name)).join(", ");
}

/** The extraction prompt embeds the cycling voltage range as one entry
 * inside experimentalPerformance (metric e.g. "Cycle 전압 범위") rather than
 * as its own field - find it by metric name instead of assuming position. */
export function findVoltageRange(entries: ExperimentalPerformanceEntry[]): string {
  const entry = entries.find((e) => /전압|voltage/i.test(e.metric));
  return entry?.value.trim() || NO_INFO;
}

/** Best-effort numeric extraction from a free-text ratio string (e.g.
 * "20 vol%", "1.2 M", "1 (molar ratio)"). Prefers a number attached to a
 * concentration unit (wt%/vol%/%/M); falls back to the first bare number
 * for molar-ratio-style values with no unit symbol. Not a real chemistry
 * parser: when several additives in the same paper share one combined
 * ratio string (e.g. "LiFSI:1.2 DME:3 FB" describing all three at once),
 * this can only find ONE number and may misattribute it to the wrong
 * additive - a known limitation, same spirit as splitElectrolyteBase's. */
export function parseAdditiveConcentration(ratio: string): number | null {
  if (!ratio || ratio === NO_INFO) return null;
  const withUnit = ratio.match(/(\d+(?:\.\d+)?)\s*(?:wt%|vol%|%|M)(?![a-zA-Z])/i);
  if (withUnit) return parseFloat(withUnit[1]);
  const bareNumber = ratio.match(/(\d+(?:\.\d+)?)/);
  return bareNumber ? parseFloat(bareNumber[1]) : null;
}

/** Finds the first entry that reads as a capacity-retention result (by
 * metric name or, failing that, by the word "retention" showing up in the
 * value itself - some papers only mention "retention" in the value, e.g.
 * "123.3 mAh g⁻¹ (retention 91.2%)"), and extracts its percentage. A paper
 * with multiple retention entries (different cell types/conditions) only
 * contributes the first one found - a deliberate simplification, not an
 * attempt to pick "the" representative number out of several valid ones. */
export function findCapacityRetentionPercent(entries: ExperimentalPerformanceEntry[]): number | null {
  const entry = entries.find((e) => /유지율|retention/i.test(e.metric) || /retention/i.test(e.value));
  if (!entry) return null;
  const match = entry.value.match(/(\d+(?:\.\d+)?)\s*%/);
  return match ? parseFloat(match[1]) : null;
}
