import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  CircleMinus,
  CirclePlus,
  Download,
  Droplets,
  ExternalLink,
  FlaskConical,
  Layers,
  Lightbulb,
  Loader2,
  Search,
  Sparkles,
} from "lucide-react";
import type { PaperEntry, PaperSummary, ResearchSuggestion } from "../../types/summarizer";
import { getResearchSuggestions, getTrendInsight } from "../../lib/summarizer/gemini";
import { downloadOverallAnalysisExcel } from "../../lib/summarizer/exportExcel";
import {
  findCapacityRetentionPercent,
  findVoltageRange,
  formatAdditives,
  parseAdditiveConcentration,
  splitElectrolyteBase,
} from "../../lib/summarizer/electrolyteAnalysis";
import { Card, Pill, SectionTitle } from "./Card";

interface OverallAnalysisViewProps {
  papers: PaperEntry[];
  apiKey: string;
}

const MIN_PAPERS = 2;
const DONUT_COLORS = ["#2563eb", "#3b82f6", "#60a5fa", "#38bdf8", "#06b6d4", "#818cf8", "#a5b4fc", "#0ea5e9"];

/** "미분류" is a valid honest answer from Gemini but isn't a real category worth charting. */
function clean(items: string[]): string[] {
  return items.filter((x) => x !== "미분류");
}

function tally(groups: string[][]): { name: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const group of groups) {
    for (const item of group) counts.set(item, (counts.get(item) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count);
}

/** Every unordered pair of distinct names within one paper's additive
 * list - e.g. [FEC, VC, LiFSI] -> [FEC,VC], [FEC,LiFSI], [VC,LiFSI]. */
function pairCombinations(names: string[]): [string, string][] {
  const unique = Array.from(new Set(names));
  const pairs: [string, string][] = [];
  for (let i = 0; i < unique.length; i++) {
    for (let j = i + 1; j < unique.length; j++) {
      pairs.push([unique[i], unique[j]]);
    }
  }
  return pairs;
}

/** Counts how many papers each additive PAIR co-occurs in - generalizes
 * the per-compound "함께 쓰인 주요 성분" panel below into a global ranking,
 * not tied to picking one compound first. A pair from a single paper
 * still shows up (count 1) - two additives formulated together in the
 * same electrolyte is itself meaningful, even before it repeats
 * elsewhere; sorting by count just lets genuinely repeated combos rise
 * to the top naturally. */
function tallyPairs(papersAdditiveNames: string[][]): { name: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const names of papersAdditiveNames) {
    for (const [a, b] of pairCombinations(names)) {
      const key = [a, b].sort().join(" + ");
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }
  return Array.from(counts.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count);
}

interface ConcentrationRetentionPoint {
  fileName: string;
  concentration: number;
  retention: number;
}

function buildConcentrationRetentionData(
  papers: (PaperEntry & { summary: PaperSummary })[],
  compound: string,
): { points: ConcentrationRetentionPoint[]; excludedCount: number } {
  const points: ConcentrationRetentionPoint[] = [];
  let excludedCount = 0;

  for (const p of papers) {
    const additive = p.summary.dashboardComponents.additivesOrCosolvents.find((a) => a.name === compound);
    if (!additive) continue;

    const concentration = parseAdditiveConcentration(additive.ratio);
    const retention = findCapacityRetentionPercent(p.summary.experimentalPerformance);
    if (concentration === null || retention === null) {
      excludedCount += 1;
      continue;
    }
    points.push({ fileName: p.fileName, concentration, retention });
  }

  return { points, excludedCount };
}

function ConcentrationRetentionScatter({
  papers,
  compound,
}: {
  papers: (PaperEntry & { summary: PaperSummary })[];
  compound: string | null;
}) {
  const { points, excludedCount } = useMemo(
    () => (compound ? buildConcentrationRetentionData(papers, compound) : { points: [], excludedCount: 0 }),
    [papers, compound],
  );

  return (
    <Card className="xl:p-8">
      <SectionTitle icon={<FlaskConical className="size-5 text-primary" />}>
        {compound ? `${compound} 농도 vs 용량 유지율` : "첨가제 농도 vs 용량 유지율"}
      </SectionTitle>
      <p className="mb-3 text-xs text-subtext">
        위 "주요 화합물 상세"에서 선택한 화합물을 기준으로, 농도(ratio)와 용량 유지율(%)을 둘 다 숫자로 해석할 수
        있는 논문만 표시합니다. 표기가 여러 화합물에 공통으로 묶여 있거나 %/M 단위가 없는 경우 정확하지 않을 수
        있습니다.
      </p>
      {!compound || points.length === 0 ? (
        <p className="py-10 text-center text-sm text-subtext">
          {compound
            ? "이 화합물은 농도-성능 관계를 그릴 수 있는 논문이 없습니다."
            : "왼쪽에서 화합물을 선택하면 표시됩니다."}
        </p>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={280}>
            <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                type="number"
                dataKey="concentration"
                name="농도"
                tick={{ fontSize: 12, fill: "#6b7280" }}
                axisLine={{ stroke: "#e5e7eb" }}
                label={{ value: "농도 (단위 혼재)", position: "insideBottom", offset: -4, fontSize: 11, fill: "#6b7280" }}
              />
              <YAxis
                type="number"
                dataKey="retention"
                name="용량 유지율(%)"
                tick={{ fontSize: 12, fill: "#6b7280" }}
                axisLine={{ stroke: "#e5e7eb" }}
                label={{ value: "용량 유지율(%)", angle: -90, position: "insideLeft", fontSize: 11, fill: "#6b7280" }}
              />
              <Tooltip
                cursor={{ strokeDasharray: "3 3" }}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const point = payload[0].payload as ConcentrationRetentionPoint;
                  return (
                    <div className="rounded-xl border border-border bg-card p-2.5 text-xs shadow-sm">
                      <p className="font-medium text-text">{point.fileName}</p>
                      <p className="mt-1 text-subtext">
                        농도 {point.concentration} · 유지율 {point.retention}%
                      </p>
                    </div>
                  );
                }}
              />
              <Scatter data={points} fill="#2563eb" />
            </ScatterChart>
          </ResponsiveContainer>
          {excludedCount > 0 && (
            <p className="mt-2 text-xs text-subtext">
              {excludedCount}개 논문은 농도 또는 용량 유지율을 숫자로 해석하지 못해 제외되었습니다.
            </p>
          )}
        </>
      )}
    </Card>
  );
}

function ElectrolyteComparisonTable({ papers }: { papers: (PaperEntry & { summary: PaperSummary })[] }) {
  return (
    <Card className="xl:p-8">
      <SectionTitle icon={<Droplets className="size-5 text-primary" />}>전해액 조성 비교</SectionTitle>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs font-semibold uppercase tracking-wide text-subtext">
              <th className="py-2 pr-3">논문</th>
              <th className="py-2 pr-3">용매 시스템</th>
              <th className="py-2 pr-3">리튬염</th>
              <th className="py-2 pr-3">첨가제</th>
              <th className="py-2 pr-3">전압범위</th>
            </tr>
          </thead>
          <tbody>
            {papers.map((p, i) => {
              const { solvent, salt } = splitElectrolyteBase(p.summary.dashboardComponents.electrolyteBase);
              const additives = formatAdditives(p.summary.dashboardComponents.additivesOrCosolvents);
              const voltage = findVoltageRange(p.summary.experimentalPerformance);
              return (
                <tr key={p.id} className="border-b border-border/60 last:border-0">
                  <td className="max-w-[220px] truncate py-2.5 pr-3 font-medium text-text" title={p.fileName}>
                    #{i + 1} {p.fileName}
                  </td>
                  <td className="py-2.5 pr-3 text-text">{solvent}</td>
                  <td className="py-2.5 pr-3 text-text">{salt}</td>
                  <td className="py-2.5 pr-3 text-text">{additives}</td>
                  <td className="py-2.5 pr-3 text-text">{voltage}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/** Vertical columns (category on the X axis) with 45°-angled labels, for
 * category names too long to fit a fixed-width Y-axis label column
 * (TopBarChart above) without truncating - e.g. "EMS (Ethyl methyl
 * sulfone) + LiPF6"-length combo names. `interval={0}` forces every label
 * to render rather than recharts silently skipping some to avoid overlap;
 * the angle + generous bottom margin/XAxis height is what actually
 * prevents that overlap. 170px was sized against the longest real combo
 * name seen in practice (~35 characters) at a 45° angle and 11px font -
 * a rough rule of thumb is roughly 0.7×(character-width×length) of
 * vertical clearance at 45°, so a long label needs noticeably more room
 * than it looks like it should. */
function AngledLabelBarChart({ data }: { data: { name: string; count: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={420}>
      <BarChart data={data} margin={{ top: 8, right: 16, bottom: 170, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
        <XAxis
          dataKey="name"
          interval={0}
          angle={-45}
          textAnchor="end"
          height={170}
          tick={{ fontSize: 11, fill: "#111827" }}
          axisLine={{ stroke: "#e5e7eb" }}
        />
        <YAxis type="number" allowDecimals={false} tick={{ fontSize: 12, fill: "#6b7280" }} axisLine={{ stroke: "#e5e7eb" }} />
        <Tooltip cursor={{ fill: "rgba(37, 99, 235, 0.06)" }} contentStyle={{ borderRadius: 12, border: "1px solid #e5e7eb", fontSize: 12 }} />
        <Bar dataKey="count" name="논문 수" fill="#2563eb" radius={[6, 6, 0, 0]} barSize={28} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function TopBarChart({ data }: { data: { name: string; count: number }[] }) {
  const height = Math.max(160, data.length * 34);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={false} />
        <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12, fill: "#6b7280" }} axisLine={{ stroke: "#e5e7eb" }} />
        <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 11, fill: "#111827" }} axisLine={{ stroke: "#e5e7eb" }} />
        <Tooltip cursor={{ fill: "rgba(37, 99, 235, 0.06)" }} contentStyle={{ borderRadius: 12, border: "1px solid #e5e7eb", fontSize: 12 }} />
        <Bar dataKey="count" name="논문 수" fill="#2563eb" radius={[0, 6, 6, 0]} barSize={16} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function DonutChart({ data }: { data: { name: string; count: number }[] }) {
  if (data.length === 0) {
    return <p className="py-16 text-center text-sm text-subtext">데이터 없음</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie data={data} dataKey="count" nameKey="name" cx="50%" cy="50%" innerRadius={50} outerRadius={85} paddingAngle={2}>
          {data.map((_, i) => (
            <Cell key={i} fill={DONUT_COLORS[i % DONUT_COLORS.length]} stroke="#ffffff" strokeWidth={1} />
          ))}
        </Pie>
        <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #e5e7eb", fontSize: 12 }} />
        <Legend layout="vertical" align="right" verticalAlign="middle" wrapperStyle={{ fontSize: 11, lineHeight: "1.6" }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function OverallAnalysisView({ papers, apiKey }: OverallAnalysisViewProps) {
  const donePapers = useMemo(
    () => papers.filter((p): p is PaperEntry & { summary: PaperSummary } => p.status === "done" && !!p.summary),
    [papers],
  );

  const additiveNames = (p: { summary: PaperSummary }) => p.summary.dashboardComponents.additivesOrCosolvents.map((a) => a.name);
  const classTags = (p: { summary: PaperSummary }) =>
    clean(p.summary.dashboardComponents.additivesOrCosolvents.flatMap((a) => a.classTags));

  const additiveTally = useMemo(() => tally(donePapers.map(additiveNames)), [donePapers]);
  const compoundClassTally = useMemo(() => tally(donePapers.map(classTags)).slice(0, 8), [donePapers]);
  const cathodeTally = useMemo(() => tally(donePapers.map((p) => clean(p.summary.dashboardComponents.cathode))).slice(0, 8), [donePapers]);
  const anodeTally = useMemo(() => tally(donePapers.map((p) => clean(p.summary.dashboardComponents.anode))).slice(0, 8), [donePapers]);
  const additivePairTally = useMemo(() => tallyPairs(donePapers.map(additiveNames)).slice(0, 8), [donePapers]);

  const [selectedCompound, setSelectedCompound] = useState<string | null>(null);

  const [suggestStatus, setSuggestStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [suggestions, setSuggestions] = useState<ResearchSuggestion[]>([]);

  const [insightStatus, setInsightStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [insights, setInsights] = useState<string[]>([]);

  if (donePapers.length < MIN_PAPERS) {
    return (
      <Card className="xl:p-8">
        <div className="flex flex-col items-center gap-2 py-10 text-center">
          <Layers className="size-8 text-subtext/50" />
          <p className="text-sm text-subtext">
            전체 분석은 완료된 논문이 {MIN_PAPERS}편 이상일 때 볼 수 있습니다. 논문을 더 분석해주세요.
            <br />
            (현재 {donePapers.length}편 완료)
          </p>
        </div>
      </Card>
    );
  }

  const activeCompound = selectedCompound ?? additiveTally[0]?.name ?? null;

  // Papers that mention the active compound, and the role text they gave it —
  // additives_or_cosolvents[].role already answers "what does this do here?"
  // per paper, so no extra Gemini call is needed to re-synthesize that.
  const compoundEntries = activeCompound
    ? donePapers.flatMap((p) =>
        p.summary.dashboardComponents.additivesOrCosolvents
          .filter((a) => a.name === activeCompound)
          .map((a) => ({ fileName: p.fileName, role: a.role })),
      )
    : [];
  const mentioningPapers = activeCompound
    ? donePapers.filter((p) => p.summary.dashboardComponents.additivesOrCosolvents.some((a) => a.name === activeCompound))
    : [];
  const coOccurring = activeCompound
    ? tally(mentioningPapers.map((p) => additiveNames(p).filter((n) => n !== activeCompound))).slice(0, 6)
    : [];

  async function handleFindSuggestions() {
    setSuggestStatus("loading");
    try {
      const result = await getResearchSuggestions(
        donePapers.map((p) => ({ fileName: p.fileName, summary: p.summary })),
        { apiKey },
      );
      setSuggestions(result);
      setSuggestStatus("done");
    } catch {
      setSuggestStatus("error");
    }
  }

  async function handleFindInsights() {
    setInsightStatus("loading");
    try {
      const result = await getTrendInsight(
        donePapers.map((p) => ({ fileName: p.fileName, summary: p.summary })),
        { apiKey },
      );
      setInsights(result);
      setInsightStatus("done");
    } catch {
      setInsightStatus("error");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Card className="xl:p-8">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-[32px] font-bold leading-tight text-text">전체 분석</h1>
            <p className="mt-2 text-sm text-subtext">완료된 논문 {donePapers.length}편을 종합해서 봅니다.</p>
          </div>
          <button
            type="button"
            onClick={() => downloadOverallAnalysisExcel(donePapers.map((p) => ({ fileName: p.fileName, summary: p.summary })))}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium text-text transition-colors hover:bg-black/[0.03]"
          >
            <Download className="size-3.5" />
            Excel 다운로드
          </button>
        </div>
      </Card>

      <ElectrolyteComparisonTable papers={donePapers} />

      <Card className="xl:p-8">
        <SectionTitle icon={<FlaskConical className="size-5 text-primary" />}>첨가제 조합 빈도 TOP 8</SectionTitle>
        {additivePairTally.length === 0 ? (
          <p className="text-sm text-subtext">데이터 없음 (한 논문에 첨가제/공용매가 2개 이상 있어야 조합이 생깁니다)</p>
        ) : (
          <AngledLabelBarChart data={additivePairTally} />
        )}
      </Card>

      {/* 3-column: top compounds bar / compound detail / research suggestions */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="xl:p-8">
          <SectionTitle icon={<FlaskConical className="size-5 text-primary" />}>핵심 첨가제/화합물 TOP 8</SectionTitle>
          <TopBarChart data={additiveTally.slice(0, 8)} />
        </Card>

        <Card className="xl:p-8">
          <SectionTitle icon={<FlaskConical className="size-5 text-primary" />}>주요 화합물 상세</SectionTitle>
          {additiveTally.length === 0 ? (
            <p className="text-sm text-subtext">데이터 없음</p>
          ) : (
            <div className="flex flex-col gap-4">
              <div className="flex flex-wrap gap-1.5">
                {additiveTally.slice(0, 8).map((c) => (
                  <button
                    key={c.name}
                    type="button"
                    onClick={() => setSelectedCompound(c.name)}
                    className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                      c.name === activeCompound ? "bg-primary text-white" : "bg-black/[0.04] text-text hover:bg-black/[0.08]"
                    }`}
                  >
                    {c.name}
                  </button>
                ))}
              </div>

              <div>
                <p className="text-sm font-semibold text-text">
                  {activeCompound} <span className="font-normal text-subtext">· {compoundEntries.length}건 언급</span>
                </p>

                {/* additives_or_cosolvents[].role already answers this per paper — shown directly, no extra Gemini call. */}
                <div className="mt-2 flex flex-col gap-2">
                  {compoundEntries.map((e, i) => (
                    <div key={i} className="rounded-lg bg-black/[0.03] p-2.5">
                      <p className="text-[11px] font-medium text-subtext">{e.fileName}</p>
                      <p className="mt-0.5 text-xs leading-relaxed text-text">{e.role}</p>
                    </div>
                  ))}
                </div>
              </div>

              {coOccurring.length > 0 && (
                <div>
                  <p className="mb-1.5 text-xs font-medium text-subtext">함께 쓰인 주요 성분</p>
                  <div className="flex flex-wrap gap-1.5">
                    {coOccurring.map((c) => (
                      <Pill key={c.name}>
                        {c.name} ({c.count})
                      </Pill>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>

        <Card className="xl:p-8">
          <SectionTitle icon={<Search className="size-5 text-primary" />}>AI 기반 논문 검색 키워드 추천</SectionTitle>

          {suggestStatus === "idle" && (
            <button
              type="button"
              onClick={handleFindSuggestions}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white transition-all hover:bg-primary-hover hover:shadow-md active:scale-[0.98]"
            >
              <Search className="size-4" />
              추천 검색 키워드 찾기
            </button>
          )}
          {suggestStatus === "loading" && (
            <p className="flex items-center gap-2 text-sm text-subtext">
              <Loader2 className="size-4 animate-spin" />
              분석 중...
            </p>
          )}
          {suggestStatus === "error" && (
            <div className="text-sm text-subtext">
              <p>추천 키워드를 가져오지 못했습니다.</p>
              <button type="button" onClick={handleFindSuggestions} className="mt-1 font-medium text-primary hover:underline">
                다시 시도
              </button>
            </div>
          )}
          {suggestStatus === "done" && (
            <div className="flex max-h-80 flex-col gap-3 overflow-y-auto scrollbar-thin pr-1">
              {suggestions.map((s) => (
                <div key={s.keyword} className="rounded-xl border border-border p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="rounded-md bg-black/[0.04] px-2 py-1 font-mono text-xs text-text">{s.keyword}</span>
                    <a
                      href={`https://scholar.google.com/scholar?q=${encodeURIComponent(s.keyword)}`}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                    >
                      Scholar 검색
                      <ExternalLink className="size-3" />
                    </a>
                  </div>
                  <p className="mt-1.5 text-xs leading-relaxed text-subtext">{s.reason}</p>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <ConcentrationRetentionScatter papers={donePapers} compound={activeCompound} />

      {/* 3-column donuts */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="xl:p-8">
          <SectionTitle icon={<Droplets className="size-5 text-primary" />}>용매/전해액 시스템 TOP 8</SectionTitle>
          <DonutChart data={compoundClassTally} />
        </Card>
        <Card className="xl:p-8">
          <SectionTitle icon={<CirclePlus className="size-5 text-primary" />}>양극 소재 TOP 8</SectionTitle>
          <DonutChart data={cathodeTally} />
        </Card>
        <Card className="xl:p-8">
          <SectionTitle icon={<CircleMinus className="size-5 text-primary" />}>음극 소재 TOP 8</SectionTitle>
          <DonutChart data={anodeTally} />
        </Card>
      </div>

      {/* Trend insight */}
      <Card className="xl:p-8">
        <SectionTitle icon={<Lightbulb className="size-5 text-primary" />}>연구 트렌드 인사이트</SectionTitle>

        {insightStatus === "idle" && (
          <button
            type="button"
            onClick={handleFindInsights}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white transition-all hover:bg-primary-hover hover:shadow-md active:scale-[0.98]"
          >
            <Sparkles className="size-4" />
            트렌드 인사이트 보기
          </button>
        )}
        {insightStatus === "loading" && (
          <p className="flex items-center gap-2 text-sm text-subtext">
            <Loader2 className="size-4 animate-spin" />
            논문 경향을 분석하는 중...
          </p>
        )}
        {insightStatus === "error" && (
          <div className="text-sm text-subtext">
            <p>인사이트를 가져오지 못했습니다.</p>
            <button type="button" onClick={handleFindInsights} className="mt-1 font-medium text-primary hover:underline">
              다시 시도
            </button>
          </div>
        )}
        {insightStatus === "done" && (
          <ul className="flex flex-col gap-2">
            {insights.map((line, i) => (
              <li key={i} className="flex items-start gap-2 text-sm leading-relaxed text-text">
                <Lightbulb className="mt-0.5 size-4 shrink-0 text-primary" />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
