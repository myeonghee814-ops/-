import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, BarChart3, CheckCircle2, FileText, History, KeyRound, Loader2, X, Zap } from "lucide-react";
import { Link } from "react-router-dom";
import type { PaperEntry, PaperStatus } from "../../types/summarizer";

export type SidebarView = "detail" | "overview";

interface SidebarProps {
  papers: PaperEntry[];
  selectedPaperId: string | null;
  onSelectPaper: (id: string) => void;
  onRemovePaper: (id: string) => void;
  view: SidebarView;
  onSelectOverview: () => void;
  isOpen: boolean;
  onClose: () => void;
}

function StatusIcon({ status }: { status: PaperStatus }) {
  switch (status) {
    case "done":
      return <CheckCircle2 className="size-4 shrink-0 text-emerald-600" />;
    case "error":
      return <AlertCircle className="size-4 shrink-0 text-red-500" />;
    case "extracting":
    case "summarizing":
      return <Loader2 className="size-4 shrink-0 animate-spin text-primary" />;
    default:
      return <FileText className="size-4 shrink-0 text-subtext" />;
  }
}

function SidebarContent({
  papers,
  selectedPaperId,
  onSelectPaper,
  onRemovePaper,
  view,
  onSelectOverview,
}: Omit<SidebarProps, "isOpen" | "onClose">) {
  const doneCount = papers.filter((p) => p.status === "done").length;
  return (
    <div className="flex h-full flex-col">
      {/* Logo / title */}
      <div className="px-6 pt-6 pb-5">
        <div className="flex items-center gap-2.5">
          <div className="flex size-9 items-center justify-center rounded-xl bg-primary text-white">
            <Zap className="size-5" fill="currentColor" />
          </div>
          <div>
            <h1 className="text-[15px] font-semibold leading-tight text-text">Battery Paper Assistant</h1>
          </div>
        </div>
        <p className="mt-2.5 text-xs leading-relaxed text-subtext">
          배터리 논문 PDF를 업로드하면 전해액 개발 관점에서 핵심 내용을 정리해드립니다.
        </p>
      </div>

      {/* Overall analysis — separate view from individual paper selection */}
      <div className="px-3 pb-3">
        <button
          type="button"
          onClick={onSelectOverview}
          className={`flex w-full items-center gap-2 rounded-xl border px-3 py-2.5 text-left text-[13px] font-medium transition-colors ${
            view === "overview" ? "border-primary bg-primary/5 text-primary" : "border-transparent text-text hover:border-border hover:bg-black/[0.02]"
          }`}
        >
          <BarChart3 className="size-4 shrink-0" />
          전체 분석
          <span className="ml-auto text-xs font-normal text-subtext">{doneCount}편</span>
        </button>
      </div>

      <div className="h-px bg-border" />

      {/* Paper list */}
      <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin px-3 py-4">
        <h2 className="px-3 text-xs font-semibold uppercase tracking-wide text-subtext">업로드한 논문 ({papers.length})</h2>

        {papers.length === 0 ? (
          <p className="mt-3 px-3 text-xs leading-relaxed text-subtext">아직 업로드한 논문이 없습니다. 오른쪽에서 PDF를 올려보세요.</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-1.5">
            <AnimatePresence initial={false}>
              {papers.map((paper) => {
                const isSelected = view === "detail" && paper.id === selectedPaperId;
                return (
                  <motion.li
                    key={paper.id}
                    layout
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.15 }}
                    className="group relative"
                  >
                    <button
                      type="button"
                      onClick={() => onSelectPaper(paper.id)}
                      className={`w-full rounded-xl border px-3 py-2.5 text-left transition-colors ${
                        isSelected
                          ? "border-primary bg-primary/5"
                          : "border-transparent hover:border-border hover:bg-black/[0.02]"
                      }`}
                    >
                      <div className="flex items-start gap-2 pr-5">
                        <StatusIcon status={paper.status} />
                        <span
                          className={`min-w-0 flex-1 truncate text-[13px] leading-snug ${
                            isSelected ? "font-medium text-primary" : "text-text"
                          }`}
                          title={paper.fileName}
                        >
                          {paper.fileName}
                        </span>
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onRemovePaper(paper.id);
                      }}
                      disabled={paper.status === "summarizing"}
                      aria-label="제거"
                      className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-subtext opacity-0 transition-opacity hover:bg-black/5 hover:text-text group-hover:opacity-100 disabled:pointer-events-none disabled:opacity-0"
                    >
                      <X className="size-3.5" />
                    </button>
                  </motion.li>
                );
              })}
            </AnimatePresence>
          </ul>
        )}

        {/* Analysis history — placeholder only, no data wired up yet */}
        <div className="mt-6">
          <h2 className="flex items-center gap-1.5 px-3 text-xs font-semibold uppercase tracking-wide text-subtext">
            <History className="size-3.5" />
            분석 히스토리
          </h2>
          <p className="mt-2 px-3 text-xs leading-relaxed text-subtext/80">준비 중입니다.</p>
        </div>
      </div>

      <div className="h-px bg-border" />

      {/* Gemini API 키는 BLIP 설정 페이지에서 검색 탭과 공유해서 관리 - 여기엔 링크만 둠 */}
      <div className="px-6 py-5">
        <Link
          to="/settings"
          className="flex items-center gap-1.5 text-xs font-semibold text-subtext transition-colors hover:text-text"
        >
          <KeyRound className="size-3.5" />
          Gemini API 키 설정
        </Link>
      </div>
    </div>
  );
}

export function Sidebar(props: SidebarProps) {
  const { isOpen, onClose } = props;

  return (
    <>
      {/* Desktop: fixed sidebar */}
      <aside className="hidden w-[280px] shrink-0 border-r border-border bg-card lg:block">
        <SidebarContent {...props} />
      </aside>

      {/* Mobile/tablet: drawer */}
      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={onClose}
              className="fixed inset-0 z-40 bg-black/30 lg:hidden"
            />
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "tween", duration: 0.2 }}
              className="fixed inset-y-0 left-0 z-50 w-[280px] bg-card shadow-xl lg:hidden"
            >
              <SidebarContent {...props} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
