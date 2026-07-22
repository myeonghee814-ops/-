import * as pdfjsLib from "pdfjs-dist";
// Vite-specific: bundle the worker as its own asset and point pdf.js at the URL.
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.mjs?url";
import type { ExtractedPaper } from "../../types/summarizer";

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

/** Below this many characters per page, we assume the PDF has no real text layer (scanned image). */
const MIN_CHARS_PER_PAGE_FOR_TEXT_LAYER = 200;

/** Heading line that marks the start of the References/Bibliography section. */
const REFERENCES_HEADING = /^\s*(references|bibliography|works cited)\s*$/i;

/** Candidate figure/table caption lines, e.g. "Figure 2.", "Fig. 3:", "Table 1." */
export const CAPTION_LINE = /^\s*(fig(?:ure)?|table)\.?\s*[sS]?\d+[a-z]?\s*[:.]/i;

/** Very rough token estimate (chars / 4), good enough for batching decisions. */
export function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

/** Reconstructs a PDF.js page's text content into actual visual lines, by
 * joining items with spaces and starting a new line whenever an item's
 * y-position changes - pdf.js's own text items are often small fragments
 * (split per font run/kerning, e.g. "Figure" / " 3." / " XPS analysis" as
 * three separate items for one visual line), so testing a regex like
 * CAPTION_LINE against the raw items individually routinely misses real
 * captions. Shared by extractRawText below and figureFinder.ts's own
 * per-page caption scan, so both agree on what counts as "one line". */
export function reconstructPageLines(
  content: Awaited<ReturnType<pdfjsLib.PDFPageProxy["getTextContent"]>>,
): string[] {
  let lastY: number | null = null;
  const lines: string[] = [];
  let current = "";
  for (const item of content.items) {
    if (!("str" in item)) continue;
    const y = item.transform[5];
    if (lastY !== null && Math.abs(y - lastY) > 1) {
      lines.push(current.trim());
      current = "";
    }
    current += item.str + " ";
    lastY = y;
  }
  if (current.trim()) lines.push(current.trim());
  return lines;
}

async function extractRawText(file: File): Promise<{ text: string; hasTextLayer: boolean }> {
  const buffer = await file.arrayBuffer();
  const doc = await pdfjsLib.getDocument({ data: buffer }).promise;

  const pageTexts: string[] = [];
  for (let pageNum = 1; pageNum <= doc.numPages; pageNum++) {
    const page = await doc.getPage(pageNum);
    const content = await page.getTextContent();
    pageTexts.push(reconstructPageLines(content).join("\n"));
  }

  const text = pageTexts.join("\n");
  const avgCharsPerPage = text.length / Math.max(doc.numPages, 1);
  return { text, hasTextLayer: avgCharsPerPage >= MIN_CHARS_PER_PAGE_FOR_TEXT_LAYER };
}

/**
 * Splits raw extracted text into body vs. references, and pulls out candidate
 * figure/table caption lines as hints. This is a best-effort heuristic split
 * (PDF text extraction loses layout/column structure) — when the References
 * heading can't be found, we fall back to leaving everything in bodyText and
 * let the Gemini prompt do the section identification itself.
 */
function splitSections(rawText: string): {
  bodyText: string;
  referencesText: string;
  candidateFigureCaptions: string[];
} {
  const lines = rawText.split("\n");

  // Search from the end: the references heading should be the *last* standalone
  // occurrence (avoids matching an in-text citation like "... see references").
  let splitAt = -1;
  for (let i = lines.length - 1; i >= 0; i--) {
    if (REFERENCES_HEADING.test(lines[i])) {
      splitAt = i;
      break;
    }
  }

  const bodyLines = splitAt >= 0 ? lines.slice(0, splitAt) : lines;
  const referenceLines = splitAt >= 0 ? lines.slice(splitAt + 1) : [];

  const candidateFigureCaptions = bodyLines.filter((line) => CAPTION_LINE.test(line));

  return {
    bodyText: bodyLines.join("\n").trim(),
    referencesText: referenceLines.join("\n").trim(),
    candidateFigureCaptions,
  };
}

export async function extractPaper(id: string, file: File): Promise<ExtractedPaper> {
  const { text, hasTextLayer } = await extractRawText(file);
  const { bodyText, referencesText, candidateFigureCaptions } = splitSections(text);

  const estimatedTokens = estimateTokens(bodyText) + estimateTokens(referencesText);

  return {
    paperId: id,
    fileName: file.name,
    bodyText,
    candidateFigureCaptions,
    referencesText,
    hasTextLayer,
    estimatedTokens,
  };
}
