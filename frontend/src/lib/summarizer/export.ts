import type { PaperEntry } from "../../types/summarizer";

function summaryToMarkdown(paper: PaperEntry): string {
  const s = paper.summary;
  if (!s) return `## ${paper.fileName}\n\n_요약 없음_\n`;

  const dc = s.dashboardComponents;
  const cathode = dc.cathode.join(", ") || "정보 없음";
  const anode = dc.anode.join(", ") || "정보 없음";
  const keywords = dc.keywords.join(", ") || "정보 없음";
  const scholarKeywords = s.googleScholarKeywords.join(", ") || "정보 없음";

  const additives = dc.additivesOrCosolvents.length
    ? dc.additivesOrCosolvents
        .map((a) => `- **${a.name}** (${a.ratio}) — ${a.role} [${a.classTags.join(", ") || "미분류"}]`)
        .join("\n")
    : "- (정보 없음)";

  const performance = s.experimentalPerformance.length
    ? s.experimentalPerformance.map((e) => `- **${e.metric}** = ${e.value} (조건: ${e.condition}) — ${e.insight}`).join("\n")
    : "- (정보 없음)";

  const figures = s.figureInsights.length
    ? s.figureInsights.map((f) => `- **${f.figureNo}** (${f.analysisTool}) — ${f.coreFinding}`).join("\n")
    : "- (정보 없음)";

  const recommended = s.recommendedPapers.length
    ? s.recommendedPapers
        .map((r) => {
          const sourceLabel = r.source === "in_references" ? "본문 References" : "References에 없는 추천 (Gemini 지식)";
          const keywordsLine = r.searchKeywords.length ? `\n  - 검색 키워드: ${r.searchKeywords.join(", ")}` : "";
          return `- **${r.title}** [${sourceLabel}] — ${r.reason}${keywordsLine}`;
        })
        .join("\n")
    : "- (추천 논문 없음)";

  return `## ${paper.fileName}

- 발행 연도: ${s.year}
- DOI: ${s.doi}

### 초록
${s.abstractSummary}

### Figure별 핵심 발견
${figures}

### 전지 구성
- 베이스 전해액: ${dc.electrolyteBase}
- 전지 형태: ${dc.batteryFormFactor}
- 양극: ${cathode}
- 음극: ${anode}

### 첨가제/공용매
${additives}

### 실험 성능 지표
${performance}

### 핵심 성능 키워드
${keywords}

### Google Scholar 검색 키워드
${scholarKeywords}

### 추천 논문
${recommended}
`;
}

export function buildMarkdownReport(papers: PaperEntry[]): string {
  return papers
    .filter((p) => p.status === "done")
    .map(summaryToMarkdown)
    .join("\n---\n\n");
}

export function buildJsonReport(papers: PaperEntry[]): string {
  const data = papers
    .filter((p) => p.status === "done" && p.summary)
    .map((p) => ({ fileName: p.fileName, ...p.summary }));
  return JSON.stringify(data, null, 2);
}

export function downloadTextFile(content: string, fileName: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}
