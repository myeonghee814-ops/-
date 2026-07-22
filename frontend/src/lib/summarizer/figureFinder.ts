import * as pdfjsLib from "pdfjs-dist";
// Vite-specific: bundle the worker as its own asset and point pdf.js at the URL.
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.mjs?url";
import { CAPTION_LINE, reconstructPageLines } from "./pdfExtract";
import { MAX_RETRIES_BY_STATUS, isDailyQuotaExhausted, retryDelayMs } from "./geminiRetry";
import { PROXY_URL } from "./config";
import type { KeyFigure } from "../../types/summarizer";

const LOG_PREFIX = "[figureFinder]";

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

/** Cap on how many candidate (caption-bearing) pages we render + send to Gemini, to bound cost/latency. */
const MAX_CANDIDATE_PAGES = 8;
const RENDER_SCALE = 2;
const MODEL = "gemini-flash-latest";

interface CandidatePage {
  pageNumber: number;
  canvas: HTMLCanvasElement;
}

async function renderPageToCanvas(page: pdfjsLib.PDFPageProxy, scale: number): Promise<HTMLCanvasElement> {
  const viewport = page.getViewport({ scale });
  const canvas = document.createElement("canvas");
  canvas.width = Math.ceil(viewport.width);
  canvas.height = Math.ceil(viewport.height);
  await page.render({ canvas, viewport }).promise;
  return canvas;
}

/** Finds pages whose text contains a figure/table caption line, rendering only those (not the whole PDF).
 * Uses the same line-reconstruction as pdfExtract.ts's extractRawText (join
 * text items by y-position into real lines) - testing CAPTION_LINE against
 * pdf.js's raw, often font-run-fragmented text items directly ("Figure" /
 * " 3." / " XPS analysis" as three separate items) used to miss real
 * captions that the main summarization pipeline (which does reconstruct
 * lines) found just fine. */
async function findCandidatePages(doc: pdfjsLib.PDFDocumentProxy): Promise<CandidatePage[]> {
  const candidates: CandidatePage[] = [];
  for (let pageNum = 1; pageNum <= doc.numPages && candidates.length < MAX_CANDIDATE_PAGES; pageNum++) {
    const page = await doc.getPage(pageNum);
    const content = await page.getTextContent();
    const lines = reconstructPageLines(content);
    const hasCaption = lines.some((line) => CAPTION_LINE.test(line));
    if (!hasCaption) continue;
    const canvas = await renderPageToCanvas(page, RENDER_SCALE);
    candidates.push({ pageNumber: pageNum, canvas });
  }
  console.log(`${LOG_PREFIX} scanned ${doc.numPages} page(s), found ${candidates.length} caption-bearing candidate(s): pages [${candidates.map((c) => c.pageNumber).join(", ")}]`);
  return candidates;
}

interface GeminiFigureResult {
  imageIndex: number;
  label: string;
  box_2d: [number, number, number, number];
}

interface GenerateContentPart {
  text?: string;
  thought?: boolean;
}

interface GenerateContentResponse {
  candidates?: { content?: { parts?: GenerateContentPart[] } }[];
}

function buildPrompt(context: { abstract: string; keyFindings: string }, pageCount: number): string {
  return `아래는 한 배터리 논문의 초록과 핵심 결과 요약, 그리고 이 논문에서 Figure/Table 캡션이 있는 페이지 이미지들입니다 (총 ${pageCount}장, image 0 ~ ${pageCount - 1} 순서).

[초록]
${context.abstract}

[핵심 결과]
${context.keyFindings}

위 내용을 참고해서, 이 논문에서 가장 핵심적인 Figure를 1~2개만 선택하세요. 각 Figure마다:
- imageIndex: 그 Figure가 있는 이미지의 인덱스 (0부터 시작, 위에서 알려준 번호 그대로)
- label: 예) "Figure 2"
- box_2d: 그 Figure의 그래프/차트 영역만(캡션 텍스트는 제외) 정규화 좌표 [ymin, xmin, ymax, xmax] (0~1000, 좌상단이 원점)

를 알려주세요. 확신이 없으면 무리해서 만들어내지 말고 figures를 빈 배열로 반환하세요.`;
}

const FIGURE_RESPONSE_SCHEMA = {
  type: "OBJECT",
  properties: {
    figures: {
      type: "ARRAY",
      items: {
        type: "OBJECT",
        properties: {
          imageIndex: { type: "INTEGER" },
          label: { type: "STRING" },
          box_2d: { type: "ARRAY", items: { type: "INTEGER" } },
        },
        required: ["imageIndex", "label", "box_2d"],
      },
    },
  },
  required: ["figures"],
};

function extractText(response: GenerateContentResponse): string {
  const parts = response.candidates?.[0]?.content?.parts ?? [];
  return parts
    .filter((part) => !part.thought)
    .map((part) => part.text ?? "")
    .join("");
}

function dataUrlToBase64(dataUrl: string): string {
  return dataUrl.slice(dataUrl.indexOf(",") + 1);
}

/** Crops a rendered page canvas to a normalized [ymin, xmin, ymax, xmax] (0-1000) box. Returns null if the box is degenerate. */
function cropToDataUrl(source: HTMLCanvasElement, box: [number, number, number, number]): string | null {
  const [ymin, xmin, ymax, xmax] = box;
  const toPx = (v: number, dim: number) => Math.round((v / 1000) * dim);

  const sx = toPx(xmin, source.width);
  const sy = toPx(ymin, source.height);
  const sw = toPx(xmax, source.width) - sx;
  const sh = toPx(ymax, source.height) - sy;
  if (sw <= 0 || sh <= 0 || sx < 0 || sy < 0) return null;

  const cropCanvas = document.createElement("canvas");
  cropCanvas.width = sw;
  cropCanvas.height = sh;
  const ctx = cropCanvas.getContext("2d");
  if (!ctx) return null;
  ctx.drawImage(source, sx, sy, sw, sh, 0, 0, sw, sh);
  return cropCanvas.toDataURL("image/png");
}

interface RequestPart {
  inlineData?: { mimeType: string; data: string };
  text?: string;
}

/** Calls the proxy once, retrying on 429/500/503 with the same policy as
 * gemini.ts's callGenerateContent (geminiRetry.ts) - this call used to have
 * no retry at all, which made it fail outright on the very first quota hit
 * instead of waiting it out like the rest of the app's Gemini calls do.
 * Returns null (instead of throwing) on any non-retryable failure, since
 * findKeyFigures always degrades to an empty result rather than an error. */
async function callFigureGemini(apiKey: string, parts: RequestPart[]): Promise<GenerateContentResponse | null> {
  let attempt = 0;
  while (true) {
    const res = await fetch(PROXY_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        apiKey,
        model: MODEL,
        contents: [{ parts }],
        generationConfig: {
          responseMimeType: "application/json",
          responseSchema: FIGURE_RESPONSE_SCHEMA,
        },
      }),
    });

    if (res.ok) return (await res.json()) as GenerateContentResponse;

    const bodyText = await res.text();

    if (res.status === 429 && isDailyQuotaExhausted(bodyText)) {
      console.warn(`${LOG_PREFIX} Gemini daily quota exhausted - not retrying:`, bodyText.slice(0, 300));
      return null;
    }

    const maxRetries = MAX_RETRIES_BY_STATUS[res.status] ?? 0;
    if (attempt < maxRetries) {
      const delay = retryDelayMs(res, bodyText);
      console.warn(
        `${LOG_PREFIX} HTTP ${res.status} (attempt ${attempt + 1}/${maxRetries + 1}), retrying in ${delay}ms`,
      );
      await sleep(delay);
      attempt += 1;
      continue;
    }

    console.error(`${LOG_PREFIX} Gemini call failed: HTTP ${res.status} - ${bodyText.slice(0, 500)}`);
    return null;
  }
}

/**
 * Finds the 1-2 most important figures in a paper and returns them as cropped,
 * in-memory data URLs (never written to disk or sent anywhere but Gemini).
 * Never throws — any failure (network, parsing, no figures found) resolves to
 * an empty array so the caller can show a soft "not found" message.
 */
export async function findKeyFigures(
  file: File,
  context: { abstract: string; keyFindings: string },
  apiKey: string,
): Promise<KeyFigure[]> {
  try {
    const buffer = await file.arrayBuffer();
    const doc = await pdfjsLib.getDocument({ data: buffer }).promise;

    const candidates = await findCandidatePages(doc);
    if (candidates.length === 0) {
      console.warn(`${LOG_PREFIX} no caption-bearing pages found - nothing to send to Gemini, returning empty.`);
      return [];
    }

    const parts = [
      ...candidates.map((c) => ({
        inlineData: { mimeType: "image/png", data: dataUrlToBase64(c.canvas.toDataURL("image/png")) },
      })),
      { text: buildPrompt(context, candidates.length) },
    ];

    const response = await callFigureGemini(apiKey, parts);
    if (!response) return [];

    const text = extractText(response);
    if (!text) {
      console.warn(`${LOG_PREFIX} Gemini response had no text content:`, response);
      return [];
    }

    const parsed = JSON.parse(text) as { figures?: GeminiFigureResult[] };
    console.log(`${LOG_PREFIX} Gemini returned ${parsed.figures?.length ?? 0} figure(s):`, parsed.figures);

    const results: KeyFigure[] = [];
    for (const fig of parsed.figures ?? []) {
      const candidate = candidates[fig.imageIndex];
      if (!candidate) {
        console.warn(`${LOG_PREFIX} Gemini referenced imageIndex ${fig.imageIndex}, but only ${candidates.length} candidate page(s) were sent - skipping.`);
        continue;
      }
      const dataUrl = cropToDataUrl(candidate.canvas, fig.box_2d);
      if (!dataUrl) {
        console.warn(`${LOG_PREFIX} Gemini's box_2d for "${fig.label}" (${JSON.stringify(fig.box_2d)}) was degenerate - skipping crop.`);
        continue;
      }
      results.push({ label: fig.label, pageNumber: candidate.pageNumber, dataUrl });
    }
    return results;
  } catch (error) {
    console.error(`${LOG_PREFIX} unexpected error - returning empty:`, error);
    return [];
  }
}
