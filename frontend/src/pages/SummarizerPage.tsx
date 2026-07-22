import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Loader2, Sparkles } from "lucide-react";

import { FileUploader } from "../components/summarizer/FileUploader";
import { OverallAnalysisView } from "../components/summarizer/OverallAnalysisView";
import { PaperDetail } from "../components/summarizer/PaperDetail";
import { Sidebar, type SidebarView } from "../components/summarizer/Sidebar";
import { Topbar } from "../components/summarizer/Topbar";
import { Card } from "../components/summarizer/Card";
import { buildBatches } from "../lib/summarizer/batching";
import { extractPaper } from "../lib/summarizer/pdfExtract";
import { findKeyFigures } from "../lib/summarizer/figureFinder";
import { summarizeBatch } from "../lib/summarizer/gemini";
import { DEFAULT_BATCHING_CONFIG, type PaperEntry } from "../types/summarizer";
import { getApiKey } from "../lib/apiKey";

function newPaperId(): string {
  return crypto.randomUUID();
}

export default function SummarizerPage() {
  // Read fresh on every mount (navigating here from another tab/page
  // remounts this component) rather than keeping local state in sync with
  // storage - the key is managed in one place (SettingsPage), shared with
  // the search tab.
  const apiKey = getApiKey();

  const [papers, setPapers] = useState<PaperEntry[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [selectedPaperId, setSelectedPaperId] = useState<string | null>(null);
  const [view, setView] = useState<SidebarView>("detail");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  function handleSelectPaper(id: string) {
    setSelectedPaperId(id);
    setView("detail");
  }

  function updatePaper(id: string, patch: Partial<PaperEntry>) {
    setPapers((prev) => prev.map((p) => (p.id === id ? { ...p, ...patch } : p)));
  }

  async function handleFilesAdded(files: File[]) {
    const entries: PaperEntry[] = files.map((file) => ({
      id: newPaperId(),
      file,
      fileName: file.name,
      status: "pending",
    }));
    setPapers((prev) => [...prev, ...entries]);

    for (const entry of entries) {
      updatePaper(entry.id, { status: "extracting" });
      try {
        const extracted = await extractPaper(entry.id, entry.file);
        updatePaper(entry.id, {
          status: "extracted",
          extracted,
          errorMessage: extracted.hasTextLayer
            ? undefined
            : "텍스트 레이어가 거의 없습니다. 스캔본일 수 있으며 결과 품질이 낮을 수 있습니다.",
        });
      } catch (error) {
        updatePaper(entry.id, {
          status: "error",
          errorMessage: error instanceof Error ? error.message : "PDF 텍스트 추출 실패",
        });
      }
    }
  }

  function handleRemove(id: string) {
    setPapers((prev) => prev.filter((p) => p.id !== id));
    setSelectedPaperId((prev) => (prev === id ? null : prev));
  }

  async function handleFindKeyFigures(paperId: string) {
    const paper = papers.find((p) => p.id === paperId);
    if (!paper || !paper.summary) return;

    updatePaper(paperId, { keyFiguresStatus: "loading" });
    try {
      const figures = await findKeyFigures(
        paper.file,
        {
          abstract: paper.summary.abstractSummary,
          keyFindings: paper.summary.figureInsights.map((f) => `${f.figureNo} (${f.analysisTool}): ${f.coreFinding}`).join("\n"),
        },
        apiKey,
      );
      updatePaper(paperId, { keyFiguresStatus: "done", keyFigures: figures });
    } catch {
      // findKeyFigures already catches its own errors and resolves to [], but
      // guard here too so a truly unexpected throw still degrades softly.
      updatePaper(paperId, { keyFiguresStatus: "error" });
    }
  }

  const extractedPapers = useMemo(
    () => papers.filter((p) => p.status === "extracted" && p.extracted).map((p) => p.extracted!),
    [papers],
  );

  const batches = useMemo(
    () => (extractedPapers.length > 0 ? buildBatches(extractedPapers, DEFAULT_BATCHING_CONFIG) : []),
    [extractedPapers],
  );

  const canRun = !isRunning && apiKey.trim().length > 0 && batches.length > 0;

  // Auto-select the first uploaded paper so there's always something to look at on the right.
  useEffect(() => {
    if (selectedPaperId === null && papers.length > 0) {
      setSelectedPaperId(papers[0].id);
    }
  }, [papers, selectedPaperId]);

  async function handleRun() {
    setIsRunning(true);
    try {
      for (const batch of batches) {
        const ids = batch.papers.map((p) => p.paperId);
        setPapers((prev) => prev.map((p) => (ids.includes(p.id) ? { ...p, status: "summarizing", batchIndex: batch.index } : p)));

        try {
          const results = await summarizeBatch(batch, { apiKey });
          setPapers((prev) =>
            prev.map((p) => {
              const summary = results.get(p.id);
              if (!summary) return ids.includes(p.id) ? { ...p, status: "error", errorMessage: "응답에서 이 논문 결과를 찾지 못했습니다." } : p;
              return { ...p, status: "done", summary };
            }),
          );
        } catch (error) {
          const message = error instanceof Error ? error.message : "Gemini 호출 실패";
          setPapers((prev) => prev.map((p) => (ids.includes(p.id) ? { ...p, status: "error", errorMessage: message } : p)));
        }
      }
    } finally {
      setIsRunning(false);
    }
  }

  const selectedPaper = papers.find((p) => p.id === selectedPaperId) ?? null;

  return (
    <div className="flex h-full bg-bg">
      <Sidebar
        papers={papers}
        selectedPaperId={selectedPaperId}
        onSelectPaper={handleSelectPaper}
        onRemovePaper={handleRemove}
        view={view}
        onSelectOverview={() => setView("overview")}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar papers={papers} onOpenSidebar={() => setSidebarOpen(true)} />

        <main className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
          <div className="flex flex-col gap-6 p-5 sm:p-6 lg:p-8">
            <div className="mx-auto w-full max-w-3xl">
              <FileUploader currentCount={papers.length} disabled={isRunning} onFilesAdded={handleFilesAdded} />
            </div>

            {batches.length > 0 && (
              <div className="mx-auto w-full max-w-3xl">
                <Card>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-text">
                        {batches.length}개 배치로 나눠 분석합니다 ({batches.reduce((n, b) => n + b.papers.length, 0)}편)
                      </p>
                      {!apiKey && (
                        <p className="mt-1 text-xs text-subtext">
                          Gemini API 키를 먼저 <Link to="/settings" className="text-primary underline">설정</Link>에서 입력하세요.
                        </p>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={handleRun}
                      disabled={!canRun}
                      className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-white transition-all hover:bg-primary-hover hover:shadow-md active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:shadow-none"
                    >
                      {isRunning ? (
                        <>
                          <Loader2 className="size-4 animate-spin" />
                          분석 진행 중...
                        </>
                      ) : (
                        <>
                          <Sparkles className="size-4" />
                          분석 시작
                        </>
                      )}
                    </button>
                  </div>
                </Card>
              </div>
            )}

            {/* The overview dashboard is information-dense and uses the full content
                width; the per-paper detail view stays at a narrower reading width. */}
            <div className={view === "overview" ? "w-full" : "mx-auto w-full max-w-3xl"}>
              {view === "overview" ? (
                <OverallAnalysisView papers={papers} apiKey={apiKey} />
              ) : selectedPaper ? (
                <PaperDetail paper={selectedPaper} onFindKeyFigures={handleFindKeyFigures} />
              ) : (
                papers.length === 0 && (
                  <div className="flex flex-col items-center gap-2 py-16 text-center">
                    <p className="text-sm text-subtext">PDF 논문을 업로드하면 여기에 분석 결과가 표시됩니다.</p>
                  </div>
                )
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
