import XLSX from "xlsx-js-style";
import JSZip from "jszip";
import type { PaperEntry, PaperSummary } from "../../types/summarizer";

// ---- styling helpers -------------------------------------------------------

const THIN_GRAY = { style: "thin" as const, color: { rgb: "D1D5DB" } };
const FULL_BORDER = { top: THIN_GRAY, bottom: THIN_GRAY, left: THIN_GRAY, right: THIN_GRAY };

/** Section banner: bold, dark-blue text on a light-blue fill — matches the app's Primary Blue tone. */
const sectionHeaderStyle = {
  font: { bold: true, color: { rgb: "1E40AF" } },
  fill: { fgColor: { rgb: "EFF6FF" } },
  alignment: { vertical: "center" as const },
};

const labelStyle = {
  font: { bold: true },
  alignment: { vertical: "top" as const },
};

const valueStyle = {
  alignment: { vertical: "top" as const, wrapText: true },
};

const tableHeaderStyle = {
  font: { bold: true, color: { rgb: "1E40AF" } },
  fill: { fgColor: { rgb: "EFF6FF" } },
  alignment: { vertical: "center" as const, wrapText: true },
  border: FULL_BORDER,
};

const tableCellStyle = {
  alignment: { vertical: "top" as const, wrapText: true },
  border: FULL_BORDER,
};

// xlsx-js-style's writer mutates the `.s` style object in place (it stamps
// resolved color/index fields directly onto whatever object you pass in). The
// style constants below (sectionHeaderStyle, tableHeaderStyle, ...) are each
// reused across dozens of cells, so every cell needs its own clone — sharing
// the same object reference caused cells to stomp on each other's resolved
// style, which is why banner cells ended up with mismatched/wrong styling.
function cell(value: string | number, style?: object) {
  return { v: value, t: typeof value === "number" ? ("n" as const) : ("s" as const), s: style ? structuredClone(style) : undefined };
}

// ---- row-height estimation --------------------------------------------------
//
// Excel *can* auto-fit row height for wrapped text on open, but that's a
// rendering-time recalculation some viewers skip — so we compute an explicit
// height instead. CHARS_PER_WCH is deliberately conservative (well under 1.0)
// because this app's text is mostly Korean, and CJK glyphs render roughly
// 1.7-2x wider than the Latin characters a "wch" column-width unit is based
// on; underestimating capacity errs toward taller rows, never clipped text.
const CHARS_PER_WCH = 0.55;
const POINTS_PER_LINE = 15;
const MIN_ROW_HEIGHT_PT = 15;
const ROW_PADDING_PT = 4;

function estimateLineCount(text: string, totalWch: number): number {
  if (!text) return 1;
  const perLine = Math.max(4, Math.floor(totalWch * CHARS_PER_WCH));
  let lines = 0;
  for (const segment of String(text).split("\n")) {
    lines += Math.max(1, Math.ceil(segment.length / perLine));
  }
  return Math.max(1, lines);
}

function heightForLines(lines: number): number {
  return Math.max(MIN_ROW_HEIGHT_PT, lines * POINTS_PER_LINE + ROW_PADDING_PT);
}

// ---- sheet builder ----------------------------------------------------------
//
// Shared across every sheet in both exports so the same fixes apply
// everywhere: (1) banner/full-width rows get a real styled cell in *every*
// column they claim to span, not just the first, so the merged band actually
// renders as a solid strip instead of a single colored cell; (2) row heights
// are computed explicitly per row from the actual column widths in play,
// instead of relying on Excel's own (unreliable) auto-fit.
function createSheetBuilder(colWidths: number[]) {
  const aoa: unknown[][] = [];
  const merges: { s: { r: number; c: number }; e: { r: number; c: number } }[] = [];
  const rows: ({ hpt: number } | undefined)[] = [];
  const totalWch = colWidths.reduce((a, b) => a + b, 0);
  const lastCol = colWidths.length - 1;

  function setHeight(r: number, lines: number) {
    rows[r] = { hpt: heightForLines(lines) };
  }

  return {
    bannerRow(title: string) {
      const r = aoa.length;
      aoa.push(colWidths.map((_, i) => cell(i === 0 ? title : "", sectionHeaderStyle)));
      merges.push({ s: { r, c: 0 }, e: { r, c: lastCol } });
      setHeight(r, estimateLineCount(title, totalWch));
    },
    labelValueRow(label: string, value: string | number, valueColIndex = 1) {
      const r = aoa.length;
      aoa.push([cell(label, labelStyle), cell(value, valueStyle)]);
      setHeight(r, estimateLineCount(String(value), colWidths[valueColIndex] ?? totalWch));
    },
    fullWidthTextRow(text: string) {
      const r = aoa.length;
      aoa.push(colWidths.map((_, i) => cell(i === 0 ? text : "", valueStyle)));
      merges.push({ s: { r, c: 0 }, e: { r, c: lastCol } });
      setHeight(r, estimateLineCount(text, totalWch));
    },
    blankRow() {
      aoa.push([]);
    },
    tableHeaderRow(headers: string[]) {
      const r = aoa.length;
      aoa.push(headers.map((h) => cell(h, tableHeaderStyle)));
      const lines = Math.max(...headers.map((h, i) => estimateLineCount(h, colWidths[i] ?? totalWch)));
      setHeight(r, lines);
    },
    tableRow(values: (string | number)[]) {
      const r = aoa.length;
      aoa.push(values.map((v) => cell(v, tableCellStyle)));
      const lines = Math.max(...values.map((v, i) => estimateLineCount(String(v), colWidths[i] ?? totalWch)));
      setHeight(r, lines);
    },
    finish(workbook: XLSX.WorkBook, sheetName: string) {
      const sheet = XLSX.utils.aoa_to_sheet(aoa);
      if (merges.length) sheet["!merges"] = merges;
      sheet["!cols"] = colWidths.map((wch) => ({ wch }));
      // Sparse array: rows we never touched are simply absent (fine at runtime for the OOXML writer).
      sheet["!rows"] = rows as XLSX.RowInfo[];
      XLSX.utils.book_append_sheet(workbook, sheet, sheetName);
      return sheet;
    },
  };
}

// ---- shared aggregation helpers ---------------------------------------------

function tally(groups: string[][]): { name: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const group of groups) {
    for (const item of group) counts.set(item, (counts.get(item) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count);
}

function clean(items: string[]): string[] {
  return items.filter((x) => x !== "미분류");
}

function safeFileName(name: string): string {
  return name.replace(/\.pdf$/i, "").replace(/[\\/:*?"<>|]/g, "_") || "paper";
}

/**
 * Post-processes an already-written .xlsx (as an ArrayBuffer) to add a frozen
 * top row to one sheet, by editing that sheet's raw XML inside the zip.
 * xlsx-js-style (like the SheetJS community edition it's forked from) has no
 * `!freeze`/`!sheetViews` write support at all — freeze panes are a Pro-only
 * feature there — so this is done by hand. Verified round-trip safe: patched
 * files re-parse cleanly and the untouched sheets are byte-for-byte the same.
 * Falls back to the unpatched bytes on any failure (freeze pane is cosmetic,
 * never worth failing the whole download over).
 */
async function withFrozenTopRow(wbArray: ArrayBuffer, sheetPosition: number): Promise<Uint8Array> {
  try {
    const zip = await JSZip.loadAsync(wbArray);
    const path = `xl/worksheets/sheet${sheetPosition}.xml`;
    const file = zip.file(path);
    if (!file) return new Uint8Array(wbArray);

    let xml = await file.async("string");
    const paneXml =
      '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/><selection pane="bottomLeft" activeCell="A2" sqref="A2"/>';

    if (/<sheetView[^>]*\/>/.test(xml)) {
      xml = xml.replace(/<sheetView([^>]*)\/>/, `<sheetView$1>${paneXml}</sheetView>`);
    } else if (/<sheetView[^>]*>/.test(xml)) {
      xml = xml.replace(/(<sheetView[^>]*>)/, `$1${paneXml}`);
    } else if (xml.includes("<sheetViews>")) {
      xml = xml.replace("<sheetViews>", `<sheetViews><sheetView workbookViewId="0">${paneXml}</sheetView>`);
    } else {
      xml = xml.replace("<sheetData", `<sheetViews><sheetView workbookViewId="0">${paneXml}</sheetView></sheetViews><sheetData`);
    }

    zip.file(path, xml);
    return await zip.generateAsync({ type: "uint8array" });
  } catch {
    return new Uint8Array(wbArray);
  }
}

function downloadBytes(bytes: Uint8Array, fileName: string) {
  const blob = new Blob([bytes.buffer as ArrayBuffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}

// ---- single paper ------------------------------------------------------------

// Column A is widened for the recommended-papers table's title column (paper
// titles run 80-150+ chars); label/value rows only ever use A+B, so A being
// wide just means some empty space after short labels — harmless.
const PAPER_COL_WCH = [45, 35, 35, 35];

/**
 * One "대시보드 요약" sheet, sectioned top-to-bottom (제목 → 기본정보 → 소재
 * 데이터 표 → 성능지표표 → Figure표 → 키워드 → 추천논문) with full-width
 * banner headers and a label/value layout (label bold in column A, value
 * wrapped in column B). Table sections get a bordered, bold header row. No
 * freeze pane here: the sheet mixes narrative sections with several tables
 * partway down, so a single top-row freeze wouldn't keep any one table's
 * header visible — freeze panes only make sense on the fully-tabular sheets
 * in the overall-analysis export.
 */
export function downloadPaperExcel(paper: PaperEntry) {
  const s = paper.summary;
  if (!s) return;
  const dc = s.dashboardComponents;

  const b = createSheetBuilder(PAPER_COL_WCH);

  // 제목
  b.bannerRow(paper.fileName);
  b.blankRow();

  // 기본정보
  b.bannerRow("기본 정보");
  b.labelValueRow("발행 연도", s.year);
  b.labelValueRow("DOI", s.doi);
  b.blankRow();
  b.fullWidthTextRow(s.abstractSummary);
  b.blankRow();

  // 소재 데이터 표
  b.bannerRow("전지 구성");
  b.labelValueRow("베이스 전해액", dc.electrolyteBase);
  b.labelValueRow("전지 형태", dc.batteryFormFactor);
  b.labelValueRow("양극", dc.cathode.join(", ") || "정보 없음");
  b.labelValueRow("음극", dc.anode.join(", ") || "정보 없음");
  b.blankRow();

  b.bannerRow("첨가제/공용매");
  b.tableHeaderRow(["이름", "비율", "역할", "계열"]);
  if (dc.additivesOrCosolvents.length === 0) {
    b.fullWidthTextRow("정보 없음");
  } else {
    for (const a of dc.additivesOrCosolvents) {
      b.tableRow([a.name, a.ratio, a.role, a.classTags.join(", ")]);
    }
  }
  b.blankRow();

  // 성능지표표
  b.bannerRow("실험 성능 지표");
  b.tableHeaderRow(["지표", "조건", "수치", "해석"]);
  if (s.experimentalPerformance.length === 0) {
    b.fullWidthTextRow("정보 없음");
  } else {
    for (const e of s.experimentalPerformance) {
      b.tableRow([e.metric, e.condition, e.value, e.insight]);
    }
  }
  b.blankRow();

  // Figure표
  b.bannerRow("Figure별 핵심 발견");
  b.tableHeaderRow(["Figure", "분석기법", "핵심 발견"]);
  if (s.figureInsights.length === 0) {
    b.fullWidthTextRow("정보 없음");
  } else {
    for (const f of s.figureInsights) {
      b.tableRow([f.figureNo, f.analysisTool, f.coreFinding]);
    }
  }
  b.blankRow();

  // 키워드
  b.bannerRow("핵심 성능 키워드");
  b.fullWidthTextRow(dc.keywords.join(", ") || "정보 없음");
  b.blankRow();

  b.bannerRow("Google Scholar 검색 키워드");
  b.fullWidthTextRow(s.googleScholarKeywords.join(", ") || "정보 없음");
  b.blankRow();

  // 추천 논문
  b.bannerRow("추천 논문");
  b.tableHeaderRow(["제목", "출처", "이유", "검색 키워드"]);
  if (s.recommendedPapers.length === 0) {
    b.fullWidthTextRow("추천 논문 없음");
  } else {
    for (const r of s.recommendedPapers) {
      b.tableRow([
        r.title,
        r.source === "in_references" ? "본문 References" : "References 밖 (Gemini 지식)",
        r.reason,
        r.searchKeywords.join(", "),
      ]);
    }
  }

  const workbook = XLSX.utils.book_new();
  b.finish(workbook, "대시보드 요약");

  XLSX.writeFile(workbook, `${safeFileName(paper.fileName)}-summary.xlsx`);
}

// ---- overall analysis ---------------------------------------------------------

const SUMMARY_COL_WCH = [28, 14];
const DETAIL_COL_WCH = [30, 8, 20, 50, 50, 22, 22, 20, 20, 30, 20];
const TALLY_COL_WCH = [30, 12];

/** Three sheets: KPI summary, one row per paper (frozen header), and compound/tag tallies. */
export async function downloadOverallAnalysisExcel(papers: { fileName: string; summary: PaperSummary }[]) {
  const workbook = XLSX.utils.book_new();

  const additiveNames = (p: { summary: PaperSummary }) => p.summary.dashboardComponents.additivesOrCosolvents.map((a) => a.name);
  const classTags = (p: { summary: PaperSummary }) =>
    clean(p.summary.dashboardComponents.additivesOrCosolvents.flatMap((a) => a.classTags));

  // Sheet 1: 요약
  const summary = createSheetBuilder(SUMMARY_COL_WCH);
  summary.bannerRow("전체 분석 요약");
  summary.labelValueRow("논문 수", papers.length);
  summary.labelValueRow("핵심 키워드 종류 수", new Set(papers.flatMap((p) => p.summary.dashboardComponents.keywords)).size);
  summary.labelValueRow("핵심 첨가제 종류 수", new Set(papers.flatMap(additiveNames)).size);
  summary.labelValueRow("용매/전해액 계열 종류 수", new Set(papers.flatMap(classTags)).size);
  summary.labelValueRow("양극 소재 종류 수", new Set(papers.flatMap((p) => clean(p.summary.dashboardComponents.cathode))).size);
  summary.labelValueRow("음극 소재 종류 수", new Set(papers.flatMap((p) => clean(p.summary.dashboardComponents.anode))).size);
  summary.finish(workbook, "요약");

  // Sheet 2: 논문별 상세 (fully tabular — this is the one that gets a frozen header row)
  const detail = createSheetBuilder(DETAIL_COL_WCH);
  detail.tableHeaderRow([
    "파일명",
    "발행연도",
    "DOI",
    "초록",
    "베이스 전해액",
    "전지 형태",
    "양극",
    "음극",
    "첨가제/공용매",
    "성능 키워드",
    "계열 태그",
  ]);
  for (const p of papers) {
    const dc = p.summary.dashboardComponents;
    detail.tableRow([
      p.fileName,
      p.summary.year,
      p.summary.doi,
      p.summary.abstractSummary,
      dc.electrolyteBase,
      dc.batteryFormFactor,
      dc.cathode.join(", "),
      dc.anode.join(", "),
      dc.additivesOrCosolvents.map((a) => `${a.name}(${a.ratio})`).join(", "),
      dc.keywords.join(", "),
      classTags(p).join(", "),
    ]);
  }
  detail.finish(workbook, "논문별 상세");

  // Sheet 3: 화합물/태그 집계 — several small tally tables stacked, each with its own banner + bordered header.
  const tallyBlocks: { title: string; data: { name: string; count: number }[] }[] = [
    { title: "핵심 첨가제/공용매 (additives_or_cosolvents)", data: tally(papers.map(additiveNames)) },
    { title: "첨가제/용매 계열 (class_tags)", data: tally(papers.map(classTags)) },
    { title: "양극 소재 (cathode)", data: tally(papers.map((p) => clean(p.summary.dashboardComponents.cathode))) },
    { title: "음극 소재 (anode)", data: tally(papers.map((p) => clean(p.summary.dashboardComponents.anode))) },
    { title: "핵심 성능 키워드 (keywords)", data: tally(papers.map((p) => p.summary.dashboardComponents.keywords)) },
  ];
  const tallySheetBuilder = createSheetBuilder(TALLY_COL_WCH);
  for (const block of tallyBlocks) {
    tallySheetBuilder.bannerRow(block.title);
    tallySheetBuilder.tableHeaderRow(["이름", "논문 수"]);
    for (const row of block.data) tallySheetBuilder.tableRow([row.name, row.count]);
    tallySheetBuilder.blankRow();
  }
  tallySheetBuilder.finish(workbook, "화합물 집계");

  const wbArray = XLSX.write(workbook, { bookType: "xlsx", type: "array", cellStyles: true }) as ArrayBuffer;
  // "논문별 상세" is the 2nd sheet appended, so it's xl/worksheets/sheet2.xml.
  const finalBytes = await withFrozenTopRow(wbArray, 2);
  downloadBytes(finalBytes, "battery-paper-overall-analysis.xlsx");
}
