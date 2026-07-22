/** Lifecycle of a single uploaded paper as it moves through the pipeline. */
export type PaperStatus =
  | "pending"
  | "extracting"
  | "extracted"
  | "queued"
  | "summarizing"
  | "done"
  | "error";

/** On-demand "핵심 Figure 보기" fetch state, kept separate from the main summarization status. */
export type KeyFiguresStatus = "idle" | "loading" | "done" | "error";

/** A cropped figure image, held only in browser memory as a data URL (never uploaded or saved to disk). */
export interface KeyFigure {
  label: string;
  pageNumber: number;
  dataUrl: string;
}

/** One uploaded PDF, tracked from upload through to final summary. */
export interface PaperEntry {
  id: string;
  file: File;
  fileName: string;
  status: PaperStatus;
  errorMessage?: string;
  extracted?: ExtractedPaper;
  summary?: PaperSummary;
  /** Which batch index this paper was sent in, once assigned. */
  batchIndex?: number;
  keyFiguresStatus?: KeyFiguresStatus;
  keyFigures?: KeyFigure[];
}

/** Result of running a PDF through PDF.js and the section-splitting heuristics. */
export interface ExtractedPaper {
  paperId: string;
  fileName: string;
  /** Main body text, with the References block (if detected) stripped out. */
  bodyText: string;
  /** Lines that look like figure/table captions, used as hints for Gemini. */
  candidateFigureCaptions: string[];
  /** Raw text of the References section, or "" if not detected. */
  referencesText: string;
  /** Whether a text layer was found at all (false => likely a scanned PDF). */
  hasTextLayer: boolean;
  /** Rough token estimate for bodyText + captions + references, used for batching. */
  estimatedTokens: number;
}

/** Whether a recommendation was actually found in the paper's own References, or is Gemini's general knowledge. */
export type RecommendationSource = "in_references" | "external_knowledge";

/** Not part of the dashboard schema below — kept as its own top-level concern (literature
 * recommendation, not material/performance data) rather than forced into dashboardComponents. */
export interface RecommendedPaper {
  title: string;
  /** "in_references": appears in this paper's References. "external_knowledge": not in References, suggested from Gemini's own knowledge of the field. */
  source: RecommendationSource;
  /** Chemical rationale: same additive/solvent family or mechanism of action, not just "same battery field". */
  reason: string;
  /** 2-3 mechanism/chemistry-focused search terms (not paper titles) for finding more papers on the same additive family. */
  searchKeywords: string[];
}

/** One solvent/salt/additive mixed into the electrolyte, alongside the base solvent. */
export interface AdditiveOrCosolvent {
  name: string;
  /** Molar/volume/mass ratio as stated in the paper (kept as free text since units/format vary). */
  ratio: string;
  /** What this component does in the formulation (SEI/CEI formation, viscosity control, etc.). */
  role: string;
  /** Chemical family tag(s) for this specific compound (e.g. "ether계", "S계(황 함유)"), or ["미분류"] if unclear. */
  classTags: string[];
}

export interface DashboardComponents {
  /** Cathode materials (e.g. "NCM811", "LFP"), or ["미분류"] if unclear. */
  cathode: string[];
  /** Anode materials (e.g. "Graphite", "Li metal"), or ["미분류"] if unclear. */
  anode: string[];
  /** The baseline electrolyte formulation (e.g. "1.2M LiPF6 in EC/EMC"). */
  electrolyteBase: string;
  additivesOrCosolvents: AdditiveOrCosolvent[];
  /** Cell form factor (coin/pouch/cylindrical/3-electrode, etc.). */
  batteryFormFactor: string;
  /** Core performance keywords (e.g. "고온성능개선", "수명개선"). */
  keywords: string[];
}

/** One quantitative performance result, paired with the harsh/test condition it was measured under. */
export interface ExperimentalPerformanceEntry {
  metric: string;
  condition: string;
  value: string;
  insight: string;
}

/** A Figure-by-figure finding: which analysis technique proved which SEI/CEI mechanism. */
export interface FigureInsight {
  figureNo: string;
  analysisTool: string;
  coreFinding: string;
}

export interface PaperSummary {
  /** Publication year, or "정보 없음" if not found on the first page/footnotes. */
  year: string;
  /** DOI, or "정보 없음" if not found. */
  doi: string;
  abstractSummary: string;
  dashboardComponents: DashboardComponents;
  experimentalPerformance: ExperimentalPerformanceEntry[];
  figureInsights: FigureInsight[];
  /** Whole-paper-topic search keywords, distinct from each recommendedPapers entry's own searchKeywords. */
  googleScholarKeywords: string[];
  recommendedPapers: RecommendedPaper[];
}

/** One Google-Scholar-ready search suggestion produced by the on-demand "전체 분석" research-direction call. */
export interface ResearchSuggestion {
  keyword: string;
  reason: string;
}

/** State of the on-demand "전체 분석" research-suggestion fetch (separate from per-paper summarization). */
export type OverallAnalysisStatus = "idle" | "loading" | "done" | "error";

/** A group of papers sent to Gemini in a single request. */
export interface Batch {
  index: number;
  papers: ExtractedPaper[];
  estimatedTokens: number;
}

export interface BatchingConfig {
  /** Hard cap on papers per batch (user asked for 3-4). */
  maxPapersPerBatch: number;
  /** Soft cap on summed estimated input tokens per batch. */
  maxTokensPerBatch: number;
}

export const DEFAULT_BATCHING_CONFIG: BatchingConfig = {
  maxPapersPerBatch: 4,
  maxTokensPerBatch: 30_000,
};

export const MAX_PAPERS = 20;
