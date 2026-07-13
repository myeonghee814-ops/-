import React, { useState } from 'react';
import { Search, FileText, Download, RefreshCw, Layers, Sliders, AlertTriangle } from 'lucide-react';

// [MOCK / DEMO DATA] AI-generated example entries for UI demonstration only.
// These are NOT verified real papers and were not retrieved from PubMed,
// Crossref, or any academic index — see mock_electrolyte_demo_data.py.
const ELECTROLYTE_DB = [
  { id: 1, chemical: "Prop-1-ene-1,3-sultone (PST)", issue: "고온 가스 발생 및 파우치 셀 부풀음", mechanism: "양극 표면에 황(S)이 풍부한 보호 CEI 피막을 형성하여 선형 카보네이트 용매의 연속 분해를 억제함.", title: "Synergistic Effect of Prop-1-ene-1,3-sultone as an Electrolyte Additive for High-Voltage Lithium-Ion Batteries", authors: "Kim, H., Lee, S., Mun, J.", keywords: ["high temperature", "gas", "pouch", "pst", "sultone"] },
  { id: 2, chemical: "Lithium difluorophosphate (LiDFP)", issue: "Li 이온 탈용매화(Desolvation) 저하 및 고속 충전 성능 약화", mechanism: "음극 SEI 필름에 이온 전도성이 높은 F 및 P 성분을 주입하여 계면 저항을 낮추고 고속 충전 성능을 개선함.", title: "Lithium Difluorophosphate as a Highly Effective Additive for Fast-Charging Cylindrical Cells", authors: "Wang, L., Zhang, Y., Kumar, P.", keywords: ["fast charge", "desolvation", "cylindrical", "lidfp", "anode"] },
  { id: 3, chemical: "Fluoroethylene carbonate (FEC)", issue: "실리콘 기반 음극의 극심한 부피 팽창 및 기계적 균열", mechanism: "실리콘 표면에 유연한 poly(FEC) 고분자 매트릭스를 형성하여 충·방전 시 발생하는 응력을 완화함.", title: "Tailoring the Polymeric SEI Film via Fluoroethylene Carbonate for High-Capacity Silicon-Graphite Anodes", authors: "Doñoro, Á., Etacheri, V., Choi, J.", keywords: ["silicon", "fec", "volume expansion", "anode", "cracking"] },
  { id: 4, chemical: "Tris(trimethylsilyl) phosphite (TMSPi)", issue: "고전압(4.5V 이상) 구동 시 HF 공격 및 전이금속(Co/Ni) 용출", mechanism: "전해액 내 잔류 수분과 유해한 HF를 효율적으로 스캐빈징(Scavenging)하여 양극 구조 붕괴를 예방함.", title: "HF-Scavenging Mechanism of Tris(trimethylsilyl) Phosphite Additive in High-Voltage LiNi0.8Co0.1Mn0.1O2 Cathodes", authors: "Jia, M., Wu, C., Ming, J.", keywords: ["high voltage", "hf", "scavenger", "tmspi", "dissolution"] },
  { id: 5, chemical: "Succinonitrile (SN)", issue: "고온(60°C 이상) 환경에서의 전해액 산화 및 열적 불안정성", mechanism: "나이트릴(-C≡N) 기가 전이금속 활성 사이트와 강한 배위 결합을 형성하여 전해액의 촉매적 산화를 차단함.", title: "Nitrile-Based Electrolyte Additive for Suppressing Catalytic Decomposition at High Temperatures", authors: "Zhang, J., Zhou, M., Zheng, J.", keywords: ["high temperature", "thermal", "sn", "nitrile", "oxidation"] },
  { id: 6, chemical: "Lithium difluoro(oxalato)borate (LiDFOB)", issue: "리튬 메탈 배터리의 불균일한 계면 부동태화 및 덴드라이트 성장", mechanism: "양극에는 B-O가 풍부한 CEI를, 리튬 메탈 음극에는 조밀한 LiF SEI를 동시에 형성하는 듀얼 계면 제어 기작.", title: "Dual-Interfacial Stabilization via Lithium Difluoro(oxalato)borate for 5V Lithium Metal Batteries", authors: "Yao, S., Xu, J., Jiang, Y.", keywords: ["lithium metal", "dendrite", "lidfob", "dual interface", "5v"] },
  { id: 7, chemical: "Vinylene carbonate (VC)", issue: "초기 화성(Formation) 공정 중 흑연 음극 표면의 지속적인 전해액 소모", mechanism: "카보네이트 용매보다 먼저 라디칼 중합 반응을 일으켜 흑연 표면에 얇고 치밀한 유기 SEI 보호막을 선제 구축함.", title: "Radical Polymerization Mechanisms of Vinylene Carbonate on Graphite Surfaces Revisited", authors: "Kim, YU., Sung, JY., Lee, JN.", keywords: ["vc", "graphite", "formation", "polymerization", "sei"] },
  { id: 8, chemical: "1,3-Propane sultone (1,3-PS)", issue: "저온 환경에서의 계면 임피던스 급증 및 출력 저하", mechanism: "황 중심의 계면 두께를 최적화하여 고온 내구성을 유지하면서도 저온에서의 Li 이온 탈용매화 저항을 낮춤.", title: "Balancing High-Temperature Safety and Low-Temperature Power via 1,3-Propane Sultone Additives", authors: "Lee, D., Lim, S., Woo, S.", keywords: ["low temperature", "impedance", "safety", "ps", "sultone"] },
  { id: 9, chemical: "Ethylene sulfate (DTD)", issue: "첫 사이클 화성 과정에서의 높은 비가역 용량 손실", mechanism: "EC 용매보다 높은 전위에서 환원 분해되어 무기 황산염 구조의 SEI를 형성, 초기 리튬 소모량을 대폭 절감함.", title: "Suppression of Irreversible Capacity Loss in Lithium-Ion Batteries using Ethylene Sulfate Additive", authors: "Zou, Y., Lv, H., Wu, X.", keywords: ["dtd", "irreversible", "capacity loss", "formation", "sulfate"] },
  { id: 10, chemical: "Adiponitrile (ADN)", issue: "하이니켈 양극재(NMC 811)의 고전압 구동 시 구조 붕괴", mechanism: "디나이트릴 구조 고유의 넓은 전위 창을 바탕으로 고산화 전위에서 니켈 원자와 착물을 형성해 산화 경로를 차단함.", title: "Stabilizing Nickel-Rich NMC 811 Cathodes up to 4.6V with Adiponitrile Electrolyte Additive", authors: "Shen, N., Wang, L., Dai, D.", keywords: ["high voltage", "nmc 811", "adn", "nickel rich", "nitrile"] }
];

export default function ElectrolyteMockScreenerApp() {
  const [keyword, setKeyword] = useState('');
  const [maxResults, setMaxResults] = useState(10);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = (e) => {
    e.preventDefault();
    if (!keyword.trim()) return;

    setLoading(true);
    setHasSearched(true);

    // UI 연출용 인위적 지연 (실제 외부 검색 없음, 로컬 배열 필터링일 뿐)
    setTimeout(() => {
      const searchTerms = keyword.toLowerCase().split(' ');
      const filtered = ELECTROLYTE_DB.filter(paper => {
        return searchTerms.some(term =>
          paper.title.toLowerCase().includes(term) ||
          paper.chemical.toLowerCase().includes(term) ||
          paper.issue.toLowerCase().includes(term) ||
          paper.keywords.some(k => k.includes(term))
        );
      }).slice(0, maxResults);

      setResults(filtered);
      setLoading(false);
    }, 1500);
  };

  return (
    <div className="p-6 max-w-6xl mx-auto bg-gray-50 min-h-screen font-sans text-gray-800">
      {/* 상단 헤더 */}
      <div className="flex items-center justify-between mb-8 pb-4 border-b border-gray-200">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-600 text-white rounded-lg">
            <Layers size={24} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">이차전지 전해액 논문 자동 스크리닝 시스템 (데모)</h1>
            <p className="text-xs text-gray-500">Electrolyte Additive & Formulation UI Demo v1.0</p>
          </div>
        </div>
        <div className="flex items-center space-x-2 text-xs bg-amber-50 text-amber-700 px-3 py-1.5 rounded-md border border-amber-200">
          <AlertTriangle size={14} />
          <span>주의: 아래 10건은 AI가 생성한 예시 데이터이며, 실제 검증된 논문이 아닙니다.</span>
        </div>
      </div>

      {/* 대시보드 레이아웃 */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">

        {/* 왼쪽 사이드바 제어 패널 */}
        <div className="lg:col-span-1 bg-white p-5 rounded-xl shadow-sm border border-gray-200 h-fit">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <Sliders size={16} /> 제어 패널
          </h2>

          <form onSubmit={handleSearch} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">연구 키워드 입력</label>
              <div className="relative">
                <input
                  type="text"
                  placeholder="예: SEI, 고온, 가스, FEC..."
                  className="w-full pl-8 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                />
                <Search className="absolute left-2.5 top-3 text-gray-400" size={14} />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">최대 검색 논문 수</label>
              <select
                className="w-full py-2 px-3 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={maxResults}
                onChange={(e) => setMaxResults(Number(e.target.value))}
              >
                <option value={5}>5개 검색</option>
                <option value={10}>10개 검색</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 text-sm rounded-lg transition-colors flex items-center justify-center gap-2 disabled:bg-blue-400"
            >
              {loading ? <RefreshCw className="animate-spin" size={14} /> : <Search size={14} />}
              {loading ? "예시 데이터 필터링 중..." : "데모 검색 시작"}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-gray-100 text-[11px] text-gray-400">
            <p>• 추천 키워드 리스트:</p>
            <div className="flex flex-wrap gap-1 mt-1.5">
              {['high temperature', 'SEI', 'high voltage', 'fast charge', 'sultone'].map(k => (
                <span
                  key={k}
                  className="bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded cursor-pointer hover:bg-gray-200"
                  onClick={() => setKeyword(k)}
                >
                  {k}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* 오른쪽 메인 데이터 결과 테이블 */}
        <div className="lg:col-span-3 space-y-4">
          {!hasSearched ? (
            <div className="bg-white border border-gray-200 rounded-xl p-12 text-center text-gray-500 shadow-sm">
              <FileText className="mx-auto text-gray-300 mb-3" size={40} />
              <p className="text-sm font-medium">검색 패널에 키워드를 입력하고 데모 검색을 시작해 주세요.</p>
              <p className="text-xs text-gray-400 mt-1">이 화면은 10건의 예시(비검증) 데이터로만 동작하는 UI 데모입니다.</p>
            </div>
          ) : loading ? (
            <div className="bg-white border border-gray-200 rounded-xl p-12 text-center text-gray-500 shadow-sm space-y-3">
              <RefreshCw className="mx-auto text-blue-600 animate-spin" size={32} />
              <p className="text-sm font-medium">로컬 예시 데이터셋에서 키워드를 매칭 중입니다...</p>
              <div className="w-48 bg-gray-200 h-1.5 rounded-full mx-auto overflow-hidden">
                <div className="bg-blue-600 h-full animate-pulse w-full"></div>
              </div>
            </div>
          ) : results.length === 0 ? (
            <div className="bg-white border border-gray-200 rounded-xl p-12 text-center text-gray-500 shadow-sm">
              <FileText className="mx-auto text-red-300 mb-3" size={40} />
              <p className="text-sm font-medium">입력하신 키워드와 매칭되는 예시 항목을 찾지 못했습니다.</p>
              <p className="text-xs text-gray-400 mt-1">다른 키워드(예: SEI, high voltage 등)로 검색해 보세요.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* 상단 액션바 */}
              <div className="flex items-center justify-between bg-white px-4 py-3 rounded-lg border border-gray-200 shadow-sm">
                <span className="text-xs text-gray-600 font-medium">
                  검색 결과: 총 <strong className="text-blue-600">{results.length}</strong>개의 예시 항목이 매칭되었습니다.
                </span>
                <button
                  onClick={() => alert('이 파일은 예시(비검증) 데이터입니다: electrolyte_MOCK_DEMO_not_real_papers.xlsx')}
                  className="flex items-center gap-1.5 bg-green-600 hover:bg-green-700 text-white text-xs font-medium py-1.5 px-3 rounded transition-colors"
                >
                  <Download size={13} /> 엑셀 파일 내보내기 (예시)
                </button>
              </div>

              {/* 논문 리스트 카드 리스트 */}
              <div className="space-y-3">
                {results.map((paper, idx) => (
                  <div key={paper.id} className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm hover:border-blue-400 transition-all">
                    {/* 카드 상단 배지 레이아웃 */}
                    <div className="flex flex-wrap gap-2 mb-2.5">
                      <span className="bg-blue-50 text-blue-700 text-[10px] font-bold uppercase px-2 py-0.5 rounded border border-blue-100">
                        No. {idx + 1}
                      </span>
                      <span className="bg-purple-50 text-purple-700 text-[10px] font-semibold px-2 py-0.5 rounded border border-purple-100">
                        🧪 핵심 소재: {paper.chemical}
                      </span>
                      <span className="bg-red-50 text-red-700 text-[10px] font-semibold px-2 py-0.5 rounded border border-red-100">
                        🎯 타겟 이슈: {paper.issue}
                      </span>
                    </div>

                    {/* 논문 서지 정보 */}
                    <h3 className="text-sm font-bold text-gray-900 mb-1 leading-snug">{paper.title}</h3>
                    <p className="text-xs text-gray-400 mb-3">{paper.authors} | 예시 데이터 (비검증)</p>

                    {/* AI 작용 기작 핵심 요약 박스 */}
                    <div className="bg-gray-50 border-l-4 border-blue-500 p-3 rounded-r-lg">
                      <h4 className="text-[11px] font-bold text-blue-700 uppercase mb-0.5">💡 AI 작용 기작 요약 (한글)</h4>
                      <p className="text-xs text-gray-700 leading-relaxed">{paper.mechanism}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
