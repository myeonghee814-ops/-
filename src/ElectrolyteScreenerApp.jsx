import React, { useState } from 'react';
import { Search, FileText, Download, RefreshCw, Layers, Sliders, ExternalLink, AlertCircle } from 'lucide-react';

const DEFAULT_KEYWORD = 'lithium battery electrolyte additive SEI';

export default function ElectrolyteScreenerApp() {
  const [keyword, setKeyword] = useState('');
  const [maxResults, setMaxResults] = useState(10);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [lastQuery, setLastQuery] = useState({ keyword: '', maxResults: 10 });

  const runSearch = async (searchKeyword, searchMax) => {
    setLoading(true);
    setError(null);
    setHasSearched(true);
    try {
      const params = new URLSearchParams({ keyword: searchKeyword, max: String(searchMax) });
      const res = await fetch(`/api/search?${params.toString()}`);
      if (!res.ok) throw new Error(`서버 오류 (${res.status})`);
      const data = await res.json();
      setResults(data);
      setLastQuery({ keyword: searchKeyword, maxResults: searchMax });
    } catch (err) {
      setError('PubMed 검색에 실패했습니다. 백엔드 서버(server.py)가 실행 중인지 확인해 주세요.');
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    const q = keyword.trim() || DEFAULT_KEYWORD;
    runSearch(q, maxResults);
  };

  const handleExport = () => {
    const params = new URLSearchParams({ keyword: lastQuery.keyword || DEFAULT_KEYWORD, max: String(lastQuery.maxResults) });
    window.open(`/api/export?${params.toString()}`, '_blank');
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
            <h1 className="text-xl font-bold text-gray-900">이차전지 전해액 논문 검색 시스템</h1>
            <p className="text-xs text-gray-500">PubMed E-utilities 기반 실시간 검색</p>
          </div>
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
                  placeholder="예: SEI, high temperature, FEC..."
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
                <option value={20}>20개 검색</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 text-sm rounded-lg transition-colors flex items-center justify-center gap-2 disabled:bg-blue-400"
            >
              {loading ? <RefreshCw className="animate-spin" size={14} /> : <Search size={14} />}
              {loading ? "PubMed 검색 중..." : "PubMed 검색 시작"}
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

        {/* 오른쪽 메인 데이터 결과 */}
        <div className="lg:col-span-3 space-y-4">
          {!hasSearched ? (
            <div className="bg-white border border-gray-200 rounded-xl p-12 text-center text-gray-500 shadow-sm">
              <FileText className="mx-auto text-gray-300 mb-3" size={40} />
              <p className="text-sm font-medium">검색 패널에 키워드를 입력하고 PubMed 검색을 시작해 주세요.</p>
              <p className="text-xs text-gray-400 mt-1">실제 PubMed E-utilities API를 통해 논문을 조회합니다.</p>
            </div>
          ) : loading ? (
            <div className="bg-white border border-gray-200 rounded-xl p-12 text-center text-gray-500 shadow-sm space-y-3">
              <RefreshCw className="mx-auto text-blue-600 animate-spin" size={32} />
              <p className="text-sm font-medium">PubMed에서 논문을 검색하는 중입니다...</p>
              <div className="w-48 bg-gray-200 h-1.5 rounded-full mx-auto overflow-hidden">
                <div className="bg-blue-600 h-full animate-pulse w-full"></div>
              </div>
            </div>
          ) : error ? (
            <div className="bg-white border border-red-200 rounded-xl p-12 text-center text-red-600 shadow-sm">
              <AlertCircle className="mx-auto text-red-300 mb-3" size={40} />
              <p className="text-sm font-medium">{error}</p>
            </div>
          ) : results.length === 0 ? (
            <div className="bg-white border border-gray-200 rounded-xl p-12 text-center text-gray-500 shadow-sm">
              <FileText className="mx-auto text-red-300 mb-3" size={40} />
              <p className="text-sm font-medium">입력하신 키워드와 매칭되는 논문을 찾지 못했습니다.</p>
              <p className="text-xs text-gray-400 mt-1">다른 키워드로 검색해 보세요.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* 상단 액션바 */}
              <div className="flex items-center justify-between bg-white px-4 py-3 rounded-lg border border-gray-200 shadow-sm">
                <span className="text-xs text-gray-600 font-medium">
                  검색 결과: 총 <strong className="text-blue-600">{results.length}</strong>개의 논문이 PubMed에서 조회되었습니다.
                </span>
                <button
                  onClick={handleExport}
                  className="flex items-center gap-1.5 bg-green-600 hover:bg-green-700 text-white text-xs font-medium py-1.5 px-3 rounded transition-colors"
                >
                  <Download size={13} /> 엑셀 파일 내보내기
                </button>
              </div>

              {/* 논문 리스트 */}
              <div className="space-y-3">
                {results.map((paper, idx) => (
                  <div key={paper.pmid || idx} className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm hover:border-blue-400 transition-all">
                    <div className="flex flex-wrap items-center gap-2 mb-2.5">
                      <span className="bg-blue-50 text-blue-700 text-[10px] font-bold uppercase px-2 py-0.5 rounded border border-blue-100">
                        No. {idx + 1}
                      </span>
                      {paper.journal && (
                        <span className="bg-gray-100 text-gray-600 text-[10px] font-semibold px-2 py-0.5 rounded border border-gray-200">
                          {paper.journal}{paper.pubdate ? ` · ${paper.pubdate}` : ''}
                        </span>
                      )}
                      {paper.url && (
                        <a
                          href={paper.url}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center gap-1 text-[10px] text-blue-600 hover:underline"
                        >
                          PubMed에서 보기 <ExternalLink size={10} />
                        </a>
                      )}
                    </div>

                    <h3 className="text-sm font-bold text-gray-900 mb-1 leading-snug">{paper.title}</h3>
                    <p className="text-xs text-gray-400 mb-3">{paper.authors}</p>

                    {paper.abstract && (
                      <div className="bg-gray-50 border-l-4 border-blue-500 p-3 rounded-r-lg">
                        <h4 className="text-[11px] font-bold text-blue-700 uppercase mb-0.5">초록 (Abstract)</h4>
                        <p className="text-xs text-gray-700 leading-relaxed">{paper.abstract}</p>
                      </div>
                    )}
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
