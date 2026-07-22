import { useRef, useState } from "react";
import {
  AlertCircle,
  ChartNoAxesColumn,
  ChevronLeft,
  ChevronRight,
  CirclePlus,
  CircleMinus,
  Download,
  ExternalLink,
  FileText,
  FlaskConical,
  ImageOff,
  Loader2,
  Microscope,
  Search,
  Tag,
  ZoomIn,
} from "lucide-react";
import type { KeyFigure, PaperEntry } from "../../types/summarizer";
import { Card, Pill, SectionTitle } from "./Card";
import { FigureLightbox } from "./FigureLightbox";
import { downloadPaperExcel } from "../../lib/summarizer/exportExcel";
import { PaperDetailSkeleton } from "./Skeleton";

function scholarSearchUrl(query: string): string {
  return `https://scholar.google.com/scholar?q=${encodeURIComponent(query)}`;
}

interface PaperDetailProps {
  paper: PaperEntry;
  onFindKeyFigures: (paperId: string) => void;
}

export function PaperDetail({ paper, onFindKeyFigures }: PaperDetailProps) {
  const [zoomedFigure, setZoomedFigure] = useState<KeyFigure | null>(null);
  const carouselRef = useRef<HTMLDivElement>(null);

  if (paper.status === "error" && !paper.summary) {
    return (
      <Card>
        <div className="flex items-start gap-3 text-red-600">
          <AlertCircle className="mt-0.5 size-5 shrink-0" />
          <div>
            <p className="font-medium">{paper.fileName}</p>
            <p className="mt-1 text-sm text-red-500/90">{paper.errorMessage ?? "처리 중 오류가 발생했습니다."}</p>
          </div>
        </div>
      </Card>
    );
  }

  if (!paper.summary) {
    return <PaperDetailSkeleton />;
  }

  const s = paper.summary;
  const dc = s.dashboardComponents;
  const figuresStatus = paper.keyFiguresStatus ?? "idle";

  function scrollCarousel(direction: 1 | -1) {
    carouselRef.current?.scrollBy({ left: direction * 320, behavior: "smooth" });
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Title / year / DOI */}
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="text-[32px] font-bold leading-tight text-text">{paper.fileName}</h1>
          <button
            type="button"
            onClick={() => downloadPaperExcel(paper)}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium text-text transition-colors hover:bg-black/[0.03]"
          >
            <Download className="size-3.5" />
            Excel 다운로드
          </button>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Pill tone="mono">{s.year}</Pill>
          {s.doi === "정보 없음" ? (
            <Pill tone="mono">DOI 정보 없음</Pill>
          ) : (
            <a
              href={`https://doi.org/${s.doi}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary/15"
            >
              {s.doi}
              <ExternalLink className="size-3" />
            </a>
          )}
        </div>
      </Card>

      {/* Abstract */}
      <Card>
        <SectionTitle icon={<FileText className="size-5 text-primary" />}>초록</SectionTitle>
        <p className="text-[15px] leading-relaxed text-text">{s.abstractSummary}</p>
      </Card>

      {/* Figure insights + on-demand Figure image summary */}
      <Card>
        <SectionTitle icon={<Microscope className="size-5 text-primary" />}>Figure별 핵심 발견</SectionTitle>
        {s.figureInsights.length ? (
          <div className="flex flex-col gap-3">
            {s.figureInsights.map((f, i) => (
              <div key={i} className="rounded-xl border border-border p-4">
                <div className="mb-1.5 flex flex-wrap items-center gap-2">
                  <span className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">{f.figureNo}</span>
                  <span className="text-xs text-subtext">{f.analysisTool}</span>
                </div>
                <p className="text-[15px] leading-relaxed text-text">{f.coreFinding}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-subtext">Figure 정보 없음</p>
        )}

        <div className="mt-6 border-t border-border pt-5">
          <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-subtext">
            <ChartNoAxesColumn className="size-4" />
            Figure Summary
          </h4>

          {figuresStatus === "idle" && (
            <button
              type="button"
              onClick={() => onFindKeyFigures(paper.id)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white transition-all hover:bg-primary-hover hover:shadow-md active:scale-[0.98]"
            >
              <ChartNoAxesColumn className="size-4" />
              핵심 Figure 보기
            </button>
          )}

          {figuresStatus === "loading" && (
            <p className="flex items-center gap-2 text-sm text-subtext">
              <Loader2 className="size-4 animate-spin" />
              Figure 찾는 중...
            </p>
          )}

          {figuresStatus === "error" && <NotFoundNote onRetry={() => onFindKeyFigures(paper.id)} />}

          {figuresStatus === "done" &&
            (paper.keyFigures && paper.keyFigures.length > 0 ? (
              <div className="flex flex-wrap gap-4">
                {paper.keyFigures.map((fig, i) => (
                  <button
                    key={`${fig.label}-${i}`}
                    type="button"
                    onClick={() => setZoomedFigure(fig)}
                    className="group relative w-full max-w-sm overflow-hidden rounded-xl border border-border text-left transition-shadow hover:shadow-md sm:w-auto"
                  >
                    <img src={fig.dataUrl} alt={fig.label} className="max-h-72 w-full object-contain bg-white" />
                    <div className="absolute right-2 top-2 rounded-full bg-black/50 p-1.5 text-white opacity-0 transition-opacity group-hover:opacity-100">
                      <ZoomIn className="size-3.5" />
                    </div>
                    <div className="border-t border-border px-3 py-2 text-xs font-medium text-subtext">
                      {fig.label} (p.{fig.pageNumber})
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <NotFoundNote onRetry={() => onFindKeyFigures(paper.id)} />
            ))}
        </div>
      </Card>

      {/* Cell composition */}
      <Card>
        <SectionTitle icon={<FlaskConical className="size-5 text-primary" />}>전지 구성</SectionTitle>
        <table className="w-full border-collapse text-sm">
          <tbody>
            <tr className="border-b border-border">
              <th className="w-40 py-3 pr-4 text-left align-top font-medium text-subtext">베이스 전해액</th>
              <td className="py-3 align-top text-text">{dc.electrolyteBase}</td>
            </tr>
            <tr>
              <th className="w-40 py-3 pr-4 text-left align-top font-medium text-subtext">전지 형태</th>
              <td className="py-3 align-top text-text">{dc.batteryFormFactor}</td>
            </tr>
          </tbody>
        </table>

        <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2">
          <div>
            <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-subtext">
              <CirclePlus className="size-3.5" />
              양극
            </p>
            <div className="flex flex-wrap gap-2">
              {dc.cathode.length ? dc.cathode.map((c) => <Pill key={c}>{c}</Pill>) : <span className="text-sm text-subtext">정보 없음</span>}
            </div>
          </div>
          <div>
            <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-subtext">
              <CircleMinus className="size-3.5" />
              음극
            </p>
            <div className="flex flex-wrap gap-2">
              {dc.anode.length ? dc.anode.map((c) => <Pill key={c}>{c}</Pill>) : <span className="text-sm text-subtext">정보 없음</span>}
            </div>
          </div>
        </div>
      </Card>

      {/* Additives / co-solvents table */}
      <Card>
        <SectionTitle icon={<FlaskConical className="size-5 text-primary" />}>첨가제/공용매</SectionTitle>
        {dc.additivesOrCosolvents.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[500px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs font-semibold text-subtext">
                  <th className="py-2 pr-3">이름</th>
                  <th className="py-2 pr-3">비율</th>
                  <th className="py-2 pr-3">역할</th>
                  <th className="py-2">계열</th>
                </tr>
              </thead>
              <tbody>
                {dc.additivesOrCosolvents.map((a, i) => (
                  <tr key={i} className="border-b border-border align-top last:border-0">
                    <td className="py-2.5 pr-3 font-medium text-text">{a.name}</td>
                    <td className="py-2.5 pr-3 text-subtext">{a.ratio}</td>
                    <td className="py-2.5 pr-3 text-text">{a.role}</td>
                    <td className="py-2.5">
                      <div className="flex flex-wrap gap-1">
                        {a.classTags.map((t) => (
                          <span key={t} className="rounded-md bg-black/[0.04] px-1.5 py-0.5 text-[11px] text-subtext">
                            {t}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-subtext">첨가제/공용매 정보 없음</p>
        )}
      </Card>

      {/* Experimental performance table */}
      <Card>
        <SectionTitle icon={<ChartNoAxesColumn className="size-5 text-primary" />}>실험 성능 지표</SectionTitle>
        {s.experimentalPerformance.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[500px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs font-semibold text-subtext">
                  <th className="py-2 pr-3">지표</th>
                  <th className="py-2 pr-3">조건</th>
                  <th className="py-2 pr-3">수치</th>
                  <th className="py-2">해석</th>
                </tr>
              </thead>
              <tbody>
                {s.experimentalPerformance.map((e, i) => (
                  <tr key={i} className="border-b border-border align-top last:border-0">
                    <td className="py-2.5 pr-3 font-medium text-text">{e.metric}</td>
                    <td className="py-2.5 pr-3 text-subtext">{e.condition}</td>
                    <td className="py-2.5 pr-3 text-text">{e.value}</td>
                    <td className="py-2.5 text-subtext">{e.insight}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-subtext">성능 지표 정보 없음</p>
        )}
      </Card>

      {/* Keywords */}
      <Card>
        <SectionTitle icon={<Tag className="size-5 text-primary" />}>키워드</SectionTitle>
        <div>
          <p className="mb-2 text-xs font-semibold text-subtext">핵심 성능 키워드</p>
          <div className="flex flex-wrap gap-2">
            {dc.keywords.length ? dc.keywords.map((k) => <Pill key={k}>{k}</Pill>) : <span className="text-sm text-subtext">정보 없음</span>}
          </div>
        </div>
        <div className="mt-4">
          <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-subtext">
            <Search className="size-3" />
            Google Scholar 검색 키워드
          </p>
          <div className="flex flex-wrap gap-2">
            {s.googleScholarKeywords.length ? (
              s.googleScholarKeywords.map((k) => (
                <a
                  key={k}
                  href={scholarSearchUrl(k)}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary/15"
                >
                  {k}
                </a>
              ))
            ) : (
              <span className="text-sm text-subtext">정보 없음</span>
            )}
          </div>
        </div>
      </Card>

      {/* Recommended papers — card carousel */}
      <Card>
        <div className="mb-4 flex items-center justify-between">
          <SectionTitle icon={<FileText className="size-5 text-primary" />}>
            <span className="mb-0">추천 논문 (같은 계열 첨가제/메커니즘)</span>
          </SectionTitle>
          {s.recommendedPapers.length > 0 && (
            <div className="flex gap-1.5">
              <button
                type="button"
                onClick={() => scrollCarousel(-1)}
                className="rounded-full border border-border p-1.5 text-subtext transition-colors hover:bg-black/[0.03] hover:text-text"
                aria-label="이전"
              >
                <ChevronLeft className="size-4" />
              </button>
              <button
                type="button"
                onClick={() => scrollCarousel(1)}
                className="rounded-full border border-border p-1.5 text-subtext transition-colors hover:bg-black/[0.03] hover:text-text"
                aria-label="다음"
              >
                <ChevronRight className="size-4" />
              </button>
            </div>
          )}
        </div>

        {s.recommendedPapers.length ? (
          <div ref={carouselRef} className="flex snap-x gap-4 overflow-x-auto scrollbar-thin pb-1">
            {s.recommendedPapers.map((r) => (
              <a
                key={r.title}
                href={scholarSearchUrl(r.title)}
                target="_blank"
                rel="noreferrer"
                className="group w-[300px] shrink-0 snap-start rounded-xl border border-border p-4 transition-colors hover:border-primary/40 hover:bg-primary/[0.02]"
              >
                <div className="mb-2">
                  {r.source === "in_references" ? (
                    <Pill tone="primary">본문 References</Pill>
                  ) : (
                    <Pill tone="mono">References 밖 (Gemini 지식)</Pill>
                  )}
                </div>
                <p className="flex items-start gap-1.5 text-sm font-medium leading-snug text-text group-hover:text-primary group-hover:underline">
                  <span>{r.title}</span>
                  <ExternalLink className="mt-0.5 size-3.5 shrink-0 text-subtext group-hover:text-primary" />
                </p>
                <p className="mt-2 text-xs leading-relaxed text-subtext">{r.reason}</p>
                {r.searchKeywords.length > 0 && (
                  <div className="mt-3 border-t border-border pt-3">
                    <p className="mb-1.5 flex items-center gap-1 text-[11px] font-semibold text-subtext">
                      <Search className="size-3" />
                      관련 검색 키워드
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {r.searchKeywords.map((kw) => (
                        <span key={kw} className="rounded-md bg-primary/10 px-2 py-0.5 font-mono text-[11px] text-primary">
                          {kw}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </a>
            ))}
          </div>
        ) : (
          <p className="text-sm text-subtext">추천 논문 없음</p>
        )}
      </Card>

      <FigureLightbox figure={zoomedFigure} onClose={() => setZoomedFigure(null)} />
    </div>
  );
}

function NotFoundNote({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex items-center gap-2 text-sm text-subtext">
      <ImageOff className="size-4" />
      <span>이 논문에서 핵심 Figure를 찾지 못했습니다.</span>
      <button type="button" onClick={onRetry} className="font-medium text-primary hover:underline">
        다시 시도
      </button>
    </div>
  );
}
