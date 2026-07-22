import type { Batch, PaperSummary, RecommendationSource, ResearchSuggestion } from "../../types/summarizer";
import {
  NO_INFO,
  findCapacityRetentionPercent,
  findVoltageRange,
  formatAdditives,
  splitElectrolyteBase,
} from "./electrolyteAnalysis";
import { MAX_RETRIES_BY_STATUS, isDailyQuotaExhausted, retryDelayMs } from "./geminiRetry";
import { PROXY_URL } from "./config";

/**
 * Rolling alias maintained by Google that always points at the current
 * recommended Flash-tier model (currently resolves to gemini-3.5-flash).
 * Pinning to a dated model id (e.g. "gemini-2.5-flash") risks the same
 * "no longer available to new users" error once that model is sunset —
 * the alias avoids that by re-pointing itself over time.
 */
export const DEFAULT_MODEL = "gemini-flash-latest";

/**
 * Neither calling Gemini directly with a header (SDK default) nor with a
 * `?key=` query param worked from this browser — both came back
 * "ACCESS_TOKEN_TYPE_UNSUPPORTED" — while the identical requests succeeded
 * from curl and from a plain Node process every time. That split points at
 * browser-specific HTTPS interception on this machine (a locally installed
 * security product's root CA is present in the Windows trust store), not
 * anything wrong with the request itself.
 *
 * So the browser no longer talks to Google directly at all. It calls the
 * Node proxy at PROXY_URL (see ./config.ts, proxy-server/index.mjs) - local
 * by default, or a deployed URL when built with VITE_GEMINI_PROXY_URL set -
 * which makes the actual Gemini call the same way our working curl tests
 * did. The API key is still entered in the browser and sent to the proxy
 * per-request; the proxy does not persist it.
 */

interface JsonSchema {
  type: "OBJECT" | "STRING" | "NUMBER" | "INTEGER" | "BOOLEAN" | "ARRAY";
  description?: string;
  properties?: Record<string, JsonSchema>;
  items?: JsonSchema;
  required?: string[];
  enum?: string[];
}

// ---- wire format (snake_case, exactly the schema the prompt was written against) ----
//
// Kept distinct from the internal camelCase PaperSummary type used throughout
// the rest of the app; mapWireToPaperSummary() converts one to the other
// right after parsing, so nothing outside this file ever sees snake_case.

interface WireAdditiveOrCosolvent {
  name: string;
  ratio: string;
  role: string;
  class_tags: string[];
}

interface WireDashboardComponents {
  cathode: string[];
  anode: string[];
  electrolyte_base: string;
  additives_or_cosolvents: WireAdditiveOrCosolvent[];
  battery_form_factor: string;
  keywords: string[];
}

interface WireExperimentalPerformanceEntry {
  metric: string;
  condition: string;
  value: string;
  insight: string;
}

interface WireFigureInsight {
  figure_no: string;
  analysis_tool: string;
  core_finding: string;
}

interface WireRecommendedPaper {
  title: string;
  source: RecommendationSource;
  reason: string;
  search_keywords: string[];
}

interface WireBasicInfo {
  file_name: string;
  year: string;
  doi: string;
  abstract_summary: string;
}

interface WirePaperSummary {
  paper_id: string;
  basic_info: WireBasicInfo;
  dashboard_components: WireDashboardComponents;
  experimental_performance: WireExperimentalPerformanceEntry[];
  figure_insights: WireFigureInsight[];
  google_scholar_keywords: string[];
  recommended_papers: WireRecommendedPaper[];
}

function mapWireToPaperSummary(wire: WirePaperSummary): PaperSummary {
  return {
    year: wire.basic_info.year,
    doi: wire.basic_info.doi,
    abstractSummary: wire.basic_info.abstract_summary,
    dashboardComponents: {
      cathode: wire.dashboard_components.cathode,
      anode: wire.dashboard_components.anode,
      electrolyteBase: wire.dashboard_components.electrolyte_base,
      additivesOrCosolvents: wire.dashboard_components.additives_or_cosolvents.map((a) => ({
        name: a.name,
        ratio: a.ratio,
        role: a.role,
        classTags: a.class_tags,
      })),
      batteryFormFactor: wire.dashboard_components.battery_form_factor,
      keywords: wire.dashboard_components.keywords,
    },
    experimentalPerformance: wire.experimental_performance.map((e) => ({
      metric: e.metric,
      condition: e.condition,
      value: e.value,
      insight: e.insight,
    })),
    figureInsights: wire.figure_insights.map((f) => ({
      figureNo: f.figure_no,
      analysisTool: f.analysis_tool,
      coreFinding: f.core_finding,
    })),
    googleScholarKeywords: wire.google_scholar_keywords,
    recommendedPapers: wire.recommended_papers.map((r) => ({
      title: r.title,
      source: r.source,
      reason: r.reason,
      searchKeywords: r.search_keywords,
    })),
  };
}

// ---- Gemini response schema (snake_case, matches the wire format above) ----

const additiveOrCosolventSchema: JsonSchema = {
  type: "OBJECT",
  properties: {
    name: { type: "STRING", description: "구체적 화학명/약어 (예: 'LiFSI', 'FEC', 'DME')." },
    ratio: { type: "STRING", description: "몰비/부피비/질량비 등 (예: '80:20 wt%', '1M'). 정보 없으면 '정보 없음'." },
    role: { type: "STRING", description: "이 성분이 전해액/전지에서 하는 역할 (예: 'SEI 형성 첨가제', '점도 조절용 공용매')." },
    class_tags: {
      type: "ARRAY",
      items: { type: "STRING" },
      description:
        "이 화합물이 속하는 화학적 계열 태그(멀티태그 가능). 예: 'ether계', 'S계(황 함유)', 'P계(인 함유)', 'F계(불소 함유)', '카보네이트계', 'nitrile계' 등 화학 지식으로 자유롭게 판단(예시에 얽매이지 말 것). 명확하지 않으면 ['미분류'].",
    },
  },
  required: ["name", "ratio", "role", "class_tags"],
};

const dashboardComponentsSchema: JsonSchema = {
  type: "OBJECT",
  properties: {
    cathode: {
      type: "ARRAY",
      items: { type: "STRING" },
      description: "양극 소재만 (예: 'NCM811', 'LFP', 'LCO'). 음극 소재는 포함하지 말 것. 명확하지 않으면 ['미분류'].",
    },
    anode: {
      type: "ARRAY",
      items: { type: "STRING" },
      description: "음극 소재만 (예: 'Graphite', 'Li metal', 'Silicon'). 양극 소재는 포함하지 말 것. 명확하지 않으면 ['미분류'].",
    },
    electrolyte_base: {
      type: "STRING",
      description: "베이스(기준) 전해액 조성 (예: '1.2M LiPF6 in EC/EMC'). 정보 없으면 '정보 없음'.",
    },
    additives_or_cosolvents: {
      type: "ARRAY",
      items: additiveOrCosolventSchema,
      description: "베이스 전해액에 섞인 공용매/희석제/첨가제/염 목록. 각 항목에 몰비/부피비/질량비를 반드시 함께 기재.",
    },
    battery_form_factor: {
      type: "STRING",
      description: "전지 형태 (예: coin cell, pouch cell, 3-electrode cell). 정보 없으면 '정보 없음'.",
    },
    keywords: {
      type: "ARRAY",
      items: { type: "STRING" },
      description: "핵심 성능 키워드 목록 (예: '고온성능개선', '수명개선').",
    },
  },
  required: ["cathode", "anode", "electrolyte_base", "additives_or_cosolvents", "battery_form_factor", "keywords"],
};

const experimentalPerformanceEntrySchema: JsonSchema = {
  type: "OBJECT",
  properties: {
    metric: { type: "STRING", description: "성능 지표명 (예: 'Capacity retention', 'Ionic conductivity', 'Cycle 전압 범위')." },
    condition: { type: "STRING", description: "측정된 가혹 조건 (온도/전류밀도/로딩/전해액량 등). 정보 없으면 '정보 없음'." },
    value: { type: "STRING", description: "정량 수치 (단위 포함, 예: '92% after 100 cycles', '1.1×10⁻³ S/cm')." },
    insight: { type: "STRING", description: "이 수치가 의미하는 바에 대한 짧은 해석." },
  },
  required: ["metric", "condition", "value", "insight"],
};

const figureInsightSchema: JsonSchema = {
  type: "OBJECT",
  properties: {
    figure_no: { type: "STRING", description: "예: 'Figure 2a', 'Figure 5'." },
    analysis_tool: { type: "STRING", description: "이 Figure에 사용된 분석기법 (예: XPS, Raman, SEM, NMR, XRD 등)." },
    core_finding: {
      type: "STRING",
      description: "이 분석기법으로 어떤 SEI/CEI 형성 메커니즘 또는 현상을 입증했는지 구체적으로 서술.",
    },
  },
  required: ["figure_no", "analysis_tool", "core_finding"],
};

const recommendedPaperSchema: JsonSchema = {
  type: "OBJECT",
  properties: {
    title: {
      type: "STRING",
      description:
        "추천 논문 제목(또는 저자+연도). source가 in_references이면 References 텍스트에 실제로 등장하는 표기를 그대로 사용하고, external_knowledge이면 실존하는 논문의 제목/저자/연도를 정확히 아는 범위에서만 제시.",
    },
    source: {
      type: "STRING",
      enum: ["in_references", "external_knowledge"],
      description:
        "in_references: 본문 References 목록에 실제로 있는, 같은 계열 첨가제/메커니즘을 다루는 논문. external_knowledge: References 안에는 조건에 맞는 게 없어서 Gemini가 아는 동일 계열 문헌 중에서 추천한 경우.",
    },
    reason: {
      type: "STRING",
      description:
        "이 논문이 관련 있는 화학적 근거. 반드시 '같은 계열의 첨가제/용매(유사한 화학 구조 또는 유사한 작용 메커니즘)라서 관련 있다'는 식으로 구체적인 화학적 유사점을 언급. 단순히 '같은 배터리 분야라서'는 불충분.",
    },
    search_keywords: {
      type: "ARRAY",
      items: { type: "STRING" },
      description:
        "이 논문과 같은 계열의 첨가제/메커니즘을 다루는 다른 논문을 찾기 위한 검색 키워드 2~3개. 논문 제목이 아니라 첨가제/메커니즘 관점의 영어 검색어.",
    },
  },
  required: ["title", "source", "reason", "search_keywords"],
};

const basicInfoSchema: JsonSchema = {
  type: "OBJECT",
  properties: {
    file_name: { type: "STRING", description: "입력으로 받은 파일명을 그대로 반환." },
    year: {
      type: "STRING",
      description:
        "논문 발행 연도. 첫 페이지 상단/하단이나 각주(예: 저널명 옆, 접수/게재 일자, copyright 표기)에서 찾으세요. 명확히 찾을 수 없으면 추측하지 말고 '정보 없음'.",
    },
    doi: {
      type: "STRING",
      description: "논문 DOI (예: 10.1021/acs.jpcc.8b03909). 명확히 찾을 수 없으면 추측하지 말고 '정보 없음'.",
    },
    abstract_summary: { type: "STRING", description: "논문 초록 요약(한국어)." },
  },
  required: ["file_name", "year", "doi", "abstract_summary"],
};

const paperSummarySchema: JsonSchema = {
  type: "OBJECT",
  properties: {
    paper_id: { type: "STRING", description: "입력으로 받은 paper_id를 그대로 반환." },
    basic_info: basicInfoSchema,
    dashboard_components: dashboardComponentsSchema,
    experimental_performance: {
      type: "ARRAY",
      items: experimentalPerformanceEntrySchema,
      description: "정량 성능 지표와 그 측정 조건의 쌍 목록.",
    },
    figure_insights: {
      type: "ARRAY",
      items: figureInsightSchema,
      description: "Figure별 분석기법과 핵심 발견.",
    },
    google_scholar_keywords: {
      type: "ARRAY",
      items: { type: "STRING" },
      description: "이 논문 전체 주제에 대한 Google Scholar 검색용 영문 키워드 3개 이상.",
    },
    recommended_papers: {
      type: "ARRAY",
      items: recommendedPaperSchema,
      description:
        "이 논문의 additives_or_cosolvents와 같은 계열(화학 구조 또는 작용 메커니즘)의 다른 첨가제를 다루는 추천 논문 목록 (최대 5개). References 우선, 없으면 external_knowledge로 보충.",
    },
  },
  required: [
    "paper_id",
    "basic_info",
    "dashboard_components",
    "experimental_performance",
    "figure_insights",
    "google_scholar_keywords",
    "recommended_papers",
  ],
};

const batchResponseSchema: JsonSchema = {
  type: "OBJECT",
  properties: {
    papers: { type: "ARRAY", items: paperSummarySchema },
  },
  required: ["papers"],
};

const SYSTEM_INSTRUCTION = `당신은 배터리 전해액 분야 수석 연구원 겸 데이터 엔지니어입니다. 여러 편의 배터리 논문 텍스트가 주어지면,
각 논문의 정량적 데이터와 소재 정보를 대시보드/엑셀에 즉시 매핑 가능한 구조로 추출합니다.

추출 규칙:
1. 용매/염/첨가제를 명확히 구분하세요. additives_or_cosolvents에는 공용매·희석제·첨가제·염을 모두 포함하고, 각 항목의 ratio에 몰비/부피비/질량비를 반드시 함께 기재하세요. class_tags에는 화학 구조 기반 계열 태그를 붙이세요 (예시에 얽매이지 말고 화학 지식으로 판단, 애매하면 여러 개, 불명확하면 ['미분류']).
2. experimental_performance의 각 항목은 정량 수치(value)와 그 수치가 측정된 가혹 조건(condition: 온도/전류밀도/로딩/전해액량 등)을 반드시 쌍으로 매칭하세요. 본문에 Cycle 시 사용된 전압 범위가 있으면 반드시 하나의 항목(metric 예: "Cycle 전압 범위")으로 포함하세요.
3. figure_insights는 Figure마다 어떤 분석기법(XPS/Raman/SEM/XRD/NMR 등)으로 어떤 SEI/CEI 형성 메커니즘 또는 현상을 입증했는지까지 구체적으로 기술하세요.
4. google_scholar_keywords는 이 논문 전체 주제에 대해 Google Scholar 검색에 바로 쓸 수 있는 영어 키워드를 3개 이상 추천하세요.

그 외 규칙:
- year/doi는 첫 페이지 상단/하단이나 각주에서 찾되, 명확히 찾을 수 없으면 추측하지 말고 '정보 없음'이라고 쓰세요.
- cathode/anode는 서로 겹치지 않게 정확히 구분하세요. 애매하면 ['미분류'].
- 모든 텍스트 항목은 한국어로 작성하세요 (google_scholar_keywords, recommended_papers의 search_keywords, doi는 예외로 원문/영어 그대로).
- 각 논문의 paper_id는 입력받은 값을 그대로 응답에 포함하세요.

recommended_papers 규칙 — 전해액 개발자 관점에서 "같은 계열 첨가제"를 찾는 게 목적입니다:
- 단순히 같은 배터리/전지 분야라는 이유로 추천하지 마세요. additives_or_cosolvents와 화학 구조 또는 작용 메커니즘이 유사한 다른 첨가제를 다루는 논문을 우선적으로 찾으세요.
- 먼저 제공된 References 텍스트 안에서 이 조건에 맞는 논문을 찾아 source를 "in_references"로 표시하세요.
- References 안에 조건에 맞는 논문이 하나도 없으면, References 밖이라도 당신이 실제로 알고 있는 동일 계열 첨가제 문헌을 추천하고 source를 "external_knowledge"로 표시하세요. 이 경우도 실존하지 않는 논문을 지어내지 말고, 확실히 아는 논문만 제시하세요.
- reason에는 반드시 화학적 근거를 포함하세요.
- search_keywords에는 논문 제목이 아니라 첨가제/메커니즘 관점의 영어 검색어를 2~3개 제시하세요.
- References와 아는 지식 모두에서 조건에 맞는 후보가 전혀 없으면 빈 배열을 반환하세요.`;

function buildBatchPrompt(batch: Batch): string {
  const paperBlocks = batch.papers
    .map((paper, i) => {
      const captionsBlock = paper.candidateFigureCaptions.length
        ? paper.candidateFigureCaptions.map((c) => `- ${c}`).join("\n")
        : "(감지된 캡션 없음 — 본문에서 직접 찾아 판단하세요)";

      return `### 논문 ${i + 1} (paper_id: ${paper.paperId}, 파일명: ${paper.fileName})

[본문 텍스트]
${paper.bodyText}

[감지된 Figure/Table 캡션 후보]
${captionsBlock}

[References 텍스트]
${paper.referencesText || "(감지된 References 섹션 없음)"}
`;
    })
    .join("\n---\n");

  return `아래는 ${batch.papers.length}편의 배터리 논문입니다. 각 논문에 대해 지정된 JSON 스키마 형식으로 응답하세요.

${paperBlocks}`;
}

export interface GeminiClientOptions {
  apiKey: string;
  model?: string;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

interface GenerateContentPart {
  text?: string;
  thought?: boolean;
}

interface GenerateContentResponse {
  candidates?: { content?: { parts?: GenerateContentPart[] } }[];
}

/** Concatenates the non-thought text parts of the first candidate, matching @google/genai's `response.text` getter. */
function extractText(response: GenerateContentResponse): string {
  const parts = response.candidates?.[0]?.content?.parts ?? [];
  return parts
    .filter((part) => !part.thought)
    .map((part) => part.text ?? "")
    .join("");
}

/** Calls the proxy once, retrying on 429/500/503 with the number of
 * retries and delay dictated by geminiRetry.ts (per-status retry count;
 * delay prefers Gemini's own suggested wait - Retry-After header or
 * RetryInfo/message text in the error body - over a guessed one). A
 * *daily* quota exhaustion is detected and surfaced immediately without
 * burning a retry on it, since no amount of waiting within one request
 * will ever clear it. */
async function callGenerateContent(
  model: string,
  apiKey: string,
  systemInstruction: string,
  prompt: string,
  schema: JsonSchema,
): Promise<GenerateContentResponse> {
  let attempt = 0;
  while (true) {
    let res: Response;
    try {
      res = await fetch(PROXY_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          apiKey,
          model,
          systemInstruction: { parts: [{ text: systemInstruction }] },
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: {
            responseMimeType: "application/json",
            responseSchema: schema,
          },
        }),
      });
    } catch {
      throw new Error(`Gemini 프록시 서버(${PROXY_URL})에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.`);
    }

    if (res.ok) return (await res.json()) as GenerateContentResponse;

    const bodyText = await res.text();

    if (res.status === 429 && isDailyQuotaExhausted(bodyText)) {
      throw new Error(
        "Gemini 무료 API 일일 요청 한도를 모두 사용했습니다. 태평양 시간 기준 자정에 초기화되며, 그 전까지는 재시도해도 성공하지 않습니다. 다른 API 키를 쓰거나 내일 다시 시도해 주세요.",
      );
    }

    const maxRetries = MAX_RETRIES_BY_STATUS[res.status] ?? 0;
    if (attempt < maxRetries) {
      const delay = retryDelayMs(res, bodyText);
      console.warn(
        `[gemini] HTTP ${res.status} (attempt ${attempt + 1}/${maxRetries + 1}), retrying in ${delay}ms`,
      );
      await sleep(delay);
      attempt += 1;
      continue;
    }

    throw new Error(`Gemini API 오류 (HTTP ${res.status}): ${bodyText}`);
  }
}

/** Calls Gemini and parses the JSON response text (retry-with-backoff already handled by callGenerateContent). */
async function generateStructured<T>(
  model: string,
  apiKey: string,
  systemInstruction: string,
  prompt: string,
  schema: JsonSchema,
): Promise<T> {
  const response = await callGenerateContent(model, apiKey, systemInstruction, prompt, schema);
  const text = extractText(response);
  if (!text) throw new Error("Gemini 응답이 비어 있습니다.");
  return JSON.parse(text) as T;
}

/**
 * Sends one batch of papers to Gemini and returns the parsed per-paper summaries,
 * keyed by paperId. Retries with exponential backoff on rate-limit/transient errors.
 */
export async function summarizeBatch(
  batch: Batch,
  options: GeminiClientOptions,
): Promise<Map<string, PaperSummary>> {
  const prompt = buildBatchPrompt(batch);
  const model = options.model ?? DEFAULT_MODEL;

  const parsed = await generateStructured<{ papers: WirePaperSummary[] }>(
    model,
    options.apiKey,
    SYSTEM_INSTRUCTION,
    prompt,
    batchResponseSchema,
  );

  const result = new Map<string, PaperSummary>();
  for (const wire of parsed.papers) {
    result.set(wire.paper_id, mapWireToPaperSummary(wire));
  }
  return result;
}

const RESEARCH_SUGGESTION_SYSTEM_INSTRUCTION = `당신은 배터리 전해액 연구원의 문헌 조사를 돕는 어시스턴트입니다.`;

const researchSuggestionSchema: JsonSchema = {
  type: "OBJECT",
  properties: {
    suggestions: {
      type: "ARRAY",
      items: {
        type: "OBJECT",
        properties: {
          keyword: { type: "STRING", description: "Google Scholar 검색에 바로 쓸 수 있는 영어 키워드 또는 짧은 구문." },
          reason: { type: "STRING", description: "이 키워드를 추천하는 이유 (한국어, 1~2문장)." },
        },
        required: ["keyword", "reason"],
      },
      description: "다음으로 찾아볼 만한 주제 3~5개.",
    },
  },
  required: ["suggestions"],
};

function summarizePaperForPrompt(p: { fileName: string; summary: PaperSummary }): string {
  const dc = p.summary.dashboardComponents;
  const additives = dc.additivesOrCosolvents
    .map((a) => `${a.name}(${a.classTags.join("/") || "미분류"})`)
    .join(", ");
  const figures = p.summary.figureInsights.map((f) => `${f.figureNo}: ${f.coreFinding}`).join(" / ");

  return `### 논문 (${p.fileName})
- 초록: ${p.summary.abstractSummary}
- 첨가제/용매: ${additives || "정보 없음"}
- 핵심 성능 키워드: ${dc.keywords.join(", ") || "정보 없음"}
- 양극: ${dc.cathode.join(", ") || "미분류"} / 음극: ${dc.anode.join(", ") || "미분류"}
- Figure 요약: ${figures || "정보 없음"}`;
}

function buildResearchSuggestionPrompt(papers: { fileName: string; summary: PaperSummary }[]): string {
  const paperBlocks = papers.map(summarizePaperForPrompt).join("\n\n");

  return `아래는 사용자가 지금까지 분석한 배터리 논문 ${papers.length}편의 요약 정보입니다.

${paperBlocks}

이 논문들의 전반적인 경향(주로 다루는 첨가제·용매 계열, 반복되는 성능 이슈, 전지 종류)을 파악해서,
사용자가 다음으로 찾아보면 좋을 주제를 Google Scholar 검색에 바로 쓸 수 있는 영어 키워드 3~5개로 추천하세요.
각 키워드마다 왜 추천하는지(예: 지금까지 카보네이트계 첨가제 위주였으니 nitrile계 비교군도 확인해볼 것을 제안 등)
1~2문장 근거를 한국어로 함께 제시하세요.`;
}

/**
 * On-demand "전체 분석" call: aggregates all completed papers' summaries and asks
 * Gemini for 3-5 Google-Scholar-ready search keywords for what to explore next.
 * Never called automatically — only when the user clicks the button.
 */
export async function getResearchSuggestions(
  papers: { fileName: string; summary: PaperSummary }[],
  options: GeminiClientOptions,
): Promise<ResearchSuggestion[]> {
  const model = options.model ?? DEFAULT_MODEL;
  const prompt = buildResearchSuggestionPrompt(papers);

  const parsed = await generateStructured<{ suggestions: ResearchSuggestion[] }>(
    model,
    options.apiKey,
    RESEARCH_SUGGESTION_SYSTEM_INSTRUCTION,
    prompt,
    researchSuggestionSchema,
  );

  return parsed.suggestions;
}

const TREND_INSIGHT_SYSTEM_INSTRUCTION = `당신은 전해액 개발 연구자를 돕는 어시스턴트입니다. 리튬염/용매/첨가제 조성, \
농도, 성능(용량 유지율 등) 데이터를 근거로 화학적으로 구체적인 인사이트를 제시합니다.`;

const trendInsightSchema: JsonSchema = {
  type: "OBJECT",
  properties: {
    insights: {
      type: "ARRAY",
      items: { type: "STRING" },
      description:
        "이 사용자가 모은 논문들의 조성/성능 데이터를 종합한 문장형 인사이트 3~5개 (한국어, 각 1문장). " +
        "예: 'FEC와 LiPF6 조합이 반복적으로 쓰이며 두 사례 모두 90% 이상의 우수한 용량 유지율을 보임'.",
    },
  },
  required: ["insights"],
};

/** Richer per-paper block than summarizePaperForPrompt above: pulls in the
 * same composition/performance signals the "전체 분석" 대시보드의 전해액 조성
 * 비교표/조합 빈도/농도-성능 산점도가 쓰는 것과 동일한 파생 로직
 * (electrolyteAnalysis.ts) 이라서, Gemini가 그 화면에서 사용자가 보는 것과
 * 같은 근거로 추론하게 됨 - 카테고리 태그만 보고 짐작하는 대신. */
function summarizeElectrolyteForPrompt(p: { fileName: string; summary: PaperSummary }): string {
  const dc = p.summary.dashboardComponents;
  const { solvent, salt } = splitElectrolyteBase(dc.electrolyteBase);
  const additives = formatAdditives(dc.additivesOrCosolvents);
  const voltage = findVoltageRange(p.summary.experimentalPerformance);
  const retention = findCapacityRetentionPercent(p.summary.experimentalPerformance);

  return `### 논문 (${p.fileName})
- 리튬염: ${salt}
- 용매 시스템: ${solvent}
- 첨가제(농도): ${additives}
- 전압범위: ${voltage}
- 용량 유지율: ${retention !== null ? `${retention}%` : NO_INFO}
- 양극: ${dc.cathode.join(", ") || "미분류"} / 음극: ${dc.anode.join(", ") || "미분류"}`;
}

function buildTrendInsightPrompt(papers: { fileName: string; summary: PaperSummary }[]): string {
  const paperBlocks = papers.map(summarizeElectrolyteForPrompt).join("\n\n");

  return `아래는 사용자가 지금까지 분석한 배터리 논문 ${papers.length}편의 전해액 조성/성능 정보입니다.

${paperBlocks}

전해액 개발 연구자 관점에서, 이 데이터를 종합한 인사이트를 문장형으로 3~5개 제시하세요. 다음 관점을 반드시 \
검토하되, 데이터가 부족해 판단할 수 없는 관점은 그냥 생략하세요:
1. 반복적으로 나타나는 리튬염/용매/첨가제 조합이 있는지, 있다면 그 조합을 쓴 논문들의 성능(용량 유지율 등)이 \
실제로 어떤지
2. 같은 첨가제라도 농도가 다른 논문들 사이에 성능 경향의 차이가 보이는지
3. 전압범위나 양극/음극 조합에 따라 눈에 띄는 차이가 있는지

데이터에 실제로 나타나는 패턴만 언급하고, 근거 없는 추측이나 "OO 연구가 증가 추세"류의 일반론은 피하세요. \
가능하면 구체적인 화합물명·수치·논문을 언급하세요.`;
}

/**
 * On-demand call for the "전체 분석" dashboard's trend-insight card: 3-5
 * sentence-style observations synthesizing the electrolyte composition/
 * combination/concentration-performance signals shown elsewhere on that
 * same dashboard (see electrolyteAnalysis.ts), not just topical keywords.
 */
export async function getTrendInsight(
  papers: { fileName: string; summary: PaperSummary }[],
  options: GeminiClientOptions,
): Promise<string[]> {
  const model = options.model ?? DEFAULT_MODEL;
  const prompt = buildTrendInsightPrompt(papers);

  const parsed = await generateStructured<{ insights: string[] }>(
    model,
    options.apiKey,
    TREND_INSIGHT_SYSTEM_INSTRUCTION,
    prompt,
    trendInsightSchema,
  );

  return parsed.insights;
}
