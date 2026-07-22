import { Download, FileDown, Menu } from "lucide-react";
import type { PaperEntry } from "../../types/summarizer";
import { buildJsonReport, buildMarkdownReport, downloadTextFile } from "../../lib/summarizer/export";

interface TopbarProps {
  papers: PaperEntry[];
  onOpenSidebar: () => void;
}

export function Topbar({ papers, onOpenSidebar }: TopbarProps) {
  const total = papers.length;
  const processed = papers.filter((p) => p.status === "done" || p.status === "error").length;
  const doneCount = papers.filter((p) => p.status === "done").length;
  const progressPct = total > 0 ? Math.round((processed / total) * 100) : 0;

  return (
    <header className="sticky top-0 z-30 flex items-center gap-4 border-b border-border bg-card/80 px-5 py-3 backdrop-blur">
      <button
        type="button"
        onClick={onOpenSidebar}
        className="rounded-lg p-1.5 text-subtext hover:bg-black/5 hover:text-text lg:hidden"
        aria-label="메뉴 열기"
      >
        <Menu className="size-5" />
      </button>

      <div className="min-w-0 flex-1">
        {total > 0 ? (
          <div className="flex items-center gap-3">
            <span className="whitespace-nowrap text-xs font-medium text-subtext">
              {processed} / {total} Papers Processed
            </span>
            <div className="h-1.5 w-32 max-w-[30vw] overflow-hidden rounded-full bg-border sm:w-40">
              <div
                className="h-full rounded-full bg-primary transition-[width] duration-500 ease-out"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>
        ) : (
          <span className="text-sm font-semibold text-text">배터리 논문 요약 도우미</span>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <button
          type="button"
          disabled={doneCount === 0}
          onClick={() => downloadTextFile(buildMarkdownReport(papers), "battery-paper-summary.md", "text/markdown")}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium text-text transition-colors hover:bg-black/[0.03] disabled:cursor-not-allowed disabled:opacity-40"
        >
          <FileDown className="size-3.5" />
          Markdown
        </button>
        <button
          type="button"
          disabled={doneCount === 0}
          onClick={() => downloadTextFile(buildJsonReport(papers), "battery-paper-summary.json", "application/json")}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium text-text transition-colors hover:bg-black/[0.03] disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Download className="size-3.5" />
          JSON
        </button>
      </div>
    </header>
  );
}
