/**
 * Offline demo data for `VITE_MOCK_API=true` builds - lets the UI be
 * previewed (e.g. by double-clicking the built index.html on Windows)
 * without the FastAPI backend or an OpenAI API key. Not used unless that
 * flag is set at build time; the real app always hits the real backend.
 */
import type { BatterySnapshot, PaperCard, PaperDetail, SearchRequest, SearchResponse } from "./types";

interface SamplePaper {
  title: string;
  authors: string;
  journal: string;
  year: number;
  doi: string;
  abstract: string;
  why_selected: string;
  battery_snapshot: BatterySnapshot;
  experimental_conditions: string;
  result_summary: string;
  /** Empty string demos the "원문 접근 불가" state - only some sample papers have one. */
  open_access_pdf_url: string;
}

const SAMPLE_PAPERS: SamplePaper[] = [
  {
    title: "Sulfur-based additive for CEI stabilization in high-voltage NCA full cells",
    authors: "Kim J, Park H, Lee S",
    journal: "Journal of Power Sources",
    year: 2025,
    doi: "10.1016/j.jpowsour.2025.234567",
    open_access_pdf_url: "https://example.com/sample-papers/sulfur-cei-stabilization.pdf",
    abstract:
      "This study investigates a sulfur-containing electrolyte additive for NCA cathodes to improve cathode-electrolyte interphase (CEI) stability and cycling performance in high-voltage lithium-ion pouch full cells.",
    why_selected:
      "고전압 NCA Full Cell을 사용하였으며, 황계 첨가제를 이용한 CEI 안정화 효과를 평가한 최신 연구입니다.",
    battery_snapshot: {
      cathode: "NCA",
      anode: "Graphite",
      electrolyte: "1M LiPF6 + 황계 첨가제",
      voltage_window: "3.0-4.3 V",
      cell_type: "파우치 풀셀",
    },
    experimental_conditions: "1C, 45도에서 200회 사이클 테스트를 진행했습니다.",
    result_summary:
      "200 사이클 후 용량 유지율 92%를 달성했습니다. 새로운 황계 첨가제가 고전압에서 전이금속 용출을 억제해 고온·고전압 조건에서 사이클 안정성이 크게 향상되었으나, 200 사이클 이후의 장기 거동은 확인되지 않았습니다.",
  },
  {
    title: "High-concentration LiFSI electrolyte enables stable silicon anode cycling",
    authors: "Choi Y, Han D",
    journal: "Nature Energy",
    year: 2024,
    doi: "10.1038/s41560-024-01543-2",
    open_access_pdf_url: "",
    abstract:
      "A high-concentration LiFSI-based electrolyte is shown to suppress silicon anode volume expansion side reactions, forming a robust SEI layer that enables stable cycling of high-capacity silicon anodes.",
    why_selected:
      "실리콘 음극의 부피 팽창 문제를 LiFSI 고농도 전해질로 해결한 연구로, SEI 안정화 메커니즘을 정량적으로 분석했습니다.",
    battery_snapshot: {
      cathode: "NCM811",
      anode: "Silicon-Graphite composite",
      electrolyte: "5M LiFSI in DME",
      voltage_window: "2.5-4.2 V",
      cell_type: "코인셀 (하프셀)",
    },
    experimental_conditions: "0.5C 정속 충방전, 상온(25도)에서 100회 사이클 진행.",
    result_summary:
      "100 사이클 후 용량 유지율 89%, 쿨롱 효율 99.5% 이상을 기록했습니다. 고농도 LiFSI 전해질이 실리콘 표면에 무기물 위주의 얇고 안정적인 SEI를 형성해 부피 팽창 문제를 전해질 설계만으로 완화했지만, 전해질 비용 상승과 점도 증가가 남은 과제입니다.",
  },
  {
    title: "TEMPO-mediated redox shuttle additive for overcharge protection in NMC cells",
    authors: "Nakamura T, Sato K, Yamada R",
    journal: "Journal of the Electrochemical Society",
    year: 2023,
    doi: "10.1149/1945-7111/acb123",
    open_access_pdf_url: "https://example.com/sample-papers/tempo-redox-shuttle.pdf",
    abstract:
      "TEMPO derivatives are evaluated as redox shuttle additives that provide reversible overcharge protection for NMC-based lithium-ion cells without degrading normal cycling performance.",
    why_selected:
      "TEMPO 기반 레독스 셔틀 첨가제의 과충전 보호 메커니즘과 정상 사이클 성능에 미치는 영향을 함께 평가한 연구입니다.",
    battery_snapshot: {
      cathode: "NMC622",
      anode: "Graphite",
      electrolyte: "1M LiPF6 + TEMPO 유도체",
      voltage_window: "3.0-4.2 V",
      cell_type: "코인셀 (풀셀)",
    },
    experimental_conditions: "1C 사이클링과 함께 과충전(4.8V) 안전성 테스트를 병행했습니다.",
    result_summary:
      "정상 사이클 용량 손실 없이 과충전 상황에서 셀 온도 상승을 억제했습니다. 가역적인 레독스 셔틀 메커니즘으로 별도 회로 없이 화학적으로 과충전을 방지할 수 있으나, 장기 저장 시 첨가제의 부반응 가능성은 추가 검증이 필요합니다.",
  },
  {
    title: "LHCE (localized high-concentration electrolyte) for 4.5V lithium metal batteries",
    authors: "Wang L, Zhang Q, Liu Y",
    journal: "Advanced Energy Materials",
    year: 2024,
    doi: "10.1002/aenm.202400987",
    open_access_pdf_url: "",
    abstract:
      "A localized high-concentration electrolyte (LHCE) formulation is developed to enable stable cycling of lithium metal anodes against high-voltage cathodes up to 4.5V.",
    why_selected:
      "리튬 금속 음극과 4.5V 고전압 양극을 동시에 안정화한 LHCE 조성 연구로, 리튬 금속 배터리 상용화에 중요한 시사점을 제공합니다.",
    battery_snapshot: {
      cathode: "고전압 NCM (4.5V)",
      anode: "Li metal",
      electrolyte: "LHCE (LiFSI/DME/TTE)",
      voltage_window: "3.0-4.5 V",
      cell_type: "코인셀 (Li metal 풀셀)",
    },
    experimental_conditions: "0.33C 충방전, 리튬 도금/탈리 효율 측정을 병행했습니다.",
    result_summary:
      "150 사이클 후 용량 유지율 85%, 리튬 쿨롱 효율 99.2%를 달성했습니다. 국소 고농도 구조의 희석 전해질로 이온전도도와 계면 안정성을 동시에 확보해 고전압 양극과 리튬 금속 음극 양쪽 모두에서 부반응이 억제되지만, 희석제(TTE)의 가격과 대량 생산 공정 검증이 아직 부족합니다.",
  },
  {
    title: "Solid-state sulfide electrolyte interface engineering for all-solid-state batteries",
    authors: "Tanaka M, Suzuki H",
    journal: "Joule",
    year: 2023,
    doi: "10.1016/j.joule.2023.05.011",
    open_access_pdf_url: "https://example.com/sample-papers/sulfide-interface-engineering.pdf",
    abstract:
      "This work addresses interfacial resistance between sulfide solid electrolytes and cathode active materials through a novel coating strategy for all-solid-state lithium batteries.",
    why_selected:
      "황화물계 고체 전해질과 양극 활물질 사이의 계면 저항 문제를 코팅 기술로 해결한 전고체전지 연구입니다.",
    battery_snapshot: {
      cathode: "NCM811 (코팅)",
      anode: "Li-In alloy",
      electrolyte: "Li6PS5Cl (황화물계 고체전해질)",
      voltage_window: "3.0-4.25 V",
      cell_type: "전고체 코인셀",
    },
    experimental_conditions: "0.1C, 상온에서 50회 사이클, 임피던스 분석을 병행했습니다.",
    result_summary:
      "계면 저항이 약 60% 감소하였고 50사이클 후 용량 유지율 94%를 기록했습니다. 산화물 나노코팅으로 황화물 전해질과 양극 사이의 부반응을 억제해 전고체전지의 고질적인 계면 저항 문제를 실질적으로 개선했지만, 코팅 공정의 대면적 균일성 확보가 실용화의 과제로 남아 있습니다.",
  },
];

let nextSearchId = 1;
let nextResultId = 1;
const searchStore = new Map<number, SearchResponse>();
const detailStore = new Map<number, PaperDetail>();

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function mockSearchPapers(request: SearchRequest): Promise<SearchResponse> {
  await delay(700);

  const keyword = [request.material, request.performance, request.additive_or_solvent]
    .map((part) => part.trim())
    .filter(Boolean)
    .join(" ");
  const searchId = nextSearchId++;
  const unranked = SAMPLE_PAPERS.map((sample, i) => ({
    sample,
    relevance_score: Math.max(60, 98 - i * 7),
  }));

  // Same priority rule as the backend: relevance is always considered,
  // sort_by only picks which of (score, year) wins ties first.
  const sorted = [...unranked].sort((a, b) => {
    const primary =
      request.sort_by === "recency"
        ? a.sample.year - b.sample.year
        : a.relevance_score - b.relevance_score;
    if (primary !== 0) return -primary;
    const secondary =
      request.sort_by === "recency"
        ? a.relevance_score - b.relevance_score
        : a.sample.year - b.sample.year;
    return -secondary;
  });

  const results: PaperCard[] = sorted.map(({ sample, relevance_score }, i) => {
    const resultId = nextResultId++;
    const card: PaperCard = {
      result_id: resultId,
      rank: i + 1,
      relevance_score,
      why_selected: sample.why_selected,
      title: sample.title,
      authors: sample.authors,
      journal: sample.journal,
      year: sample.year,
      doi: sample.doi,
      battery_snapshot: sample.battery_snapshot,
    };
    detailStore.set(resultId, {
      ...card,
      experimental_conditions: sample.experimental_conditions,
      result_summary: sample.result_summary,
      abstract: sample.abstract,
      keyword,
      open_access_pdf_url: sample.open_access_pdf_url,
      deep_analysis: null,
    });
    return card;
  });

  const response: SearchResponse = {
    search_id: searchId,
    keyword,
    material: request.material.trim(),
    material_notice: "",
    material_notice_level: null,
    performance: request.performance.trim(),
    additive_or_solvent: request.additive_or_solvent.trim(),
    additive_notice: "",
    additive_notice_level: null,
    sort_by: request.sort_by,
    expanded_query: `(${keyword}) AND (lithium battery OR electrolyte OR cathode OR anode)`,
    results,
    ai_degraded: false,
  };
  searchStore.set(searchId, response);
  return response;
}

export async function mockGetSearch(searchId: string): Promise<SearchResponse> {
  await delay(300);
  const found = searchStore.get(Number(searchId));
  if (!found) throw new Error("검색 결과를 찾을 수 없습니다.");
  return found;
}

export async function mockGetPaperDetail(resultId: string): Promise<PaperDetail> {
  await delay(300);
  const found = detailStore.get(Number(resultId));
  if (!found) throw new Error("해당 논문 결과를 찾을 수 없습니다.");
  return found;
}

export async function mockRunDeepAnalysis(resultId: string): Promise<PaperDetail> {
  await delay(1500);
  const found = detailStore.get(Number(resultId));
  if (!found) throw new Error("해당 논문 결과를 찾을 수 없습니다.");
  if (!found.open_access_pdf_url) {
    throw new Error("오픈 액세스 원문 PDF가 없어 심층 분석을 진행할 수 없습니다.");
  }

  const updated: PaperDetail = {
    ...found,
    deep_analysis: {
      base_electrolyte: found.battery_snapshot.electrolyte,
      test_electrolyte: "정보 없음",
      voltage_range: found.battery_snapshot.voltage_window,
      cell_type_detail: found.battery_snapshot.cell_type,
      key_findings: `${found.result_summary} (원문 Figure 근거 심층 분석 결과 - 데모용 목데이터입니다.)`,
      summary: found.result_summary,
    },
  };
  detailStore.set(Number(resultId), updated);
  return updated;
}
