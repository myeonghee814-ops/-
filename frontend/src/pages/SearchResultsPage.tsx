import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { getSearch, searchPapers } from "../api/client";
import ErrorMessage from "../components/ErrorMessage";
import InfoMessage from "../components/InfoMessage";
import Loading from "../components/Loading";
import PaperCard from "../components/PaperCard";
import SearchBar from "../components/SearchBar";
import WarningMessage from "../components/WarningMessage";
import type { SearchRequest, SearchResponse } from "../api/types";

export default function SearchResultsPage() {
  const { searchId } = useParams<{ searchId: string }>();
  const navigate = useNavigate();

  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!searchId) return;
    setLoading(true);
    setError(null);
    getSearch(searchId)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "검색 결과를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, [searchId]);

  async function handleNewSearch(request: SearchRequest) {
    setSearching(true);
    setError(null);
    try {
      const response = await searchPapers(request);
      navigate(`/search/${response.search_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "검색에 실패했습니다. 다시 시도해주세요.");
    } finally {
      setSearching(false);
    }
  }

  const initialValue: SearchRequest | undefined = data
    ? {
        material: data.material,
        performance: data.performance,
        additive_or_solvent: data.additive_or_solvent,
        sort_by: data.sort_by,
      }
    : undefined;

  return (
    <div className="results-page">
      <SearchBar initialValue={initialValue} loading={searching} onSubmit={handleNewSearch} />

      {loading && <Loading message="결과를 불러오는 중입니다..." />}
      {error && <ErrorMessage message={error} />}

      {data && !loading && (
        <>
          <h2 className="results-heading">
            <span>&ldquo;{data.keyword}&rdquo;</span>에 대한 상위 {data.results.length}개 논문
          </h2>
          {data.expanded_query && (
            <p className="results-expanded-query">검색어 확장: {data.expanded_query}</p>
          )}
          {data.material_notice && data.material_notice_level === "info" && (
            <InfoMessage message={data.material_notice} />
          )}
          {data.material_notice && data.material_notice_level === "warning" && (
            <WarningMessage message={data.material_notice} />
          )}
          {data.additive_notice && data.additive_notice_level === "info" && (
            <InfoMessage message={data.additive_notice} />
          )}
          {data.additive_notice && data.additive_notice_level === "warning" && (
            <WarningMessage message={data.additive_notice} />
          )}
          {data.ai_degraded && (
            <WarningMessage message="Gemini 서버가 일시적으로 혼잡합니다. 잠시 후 다시 시도해주세요." />
          )}
          <div className="paper-card-list">
            {data.results.map((paper) => (
              <PaperCard key={paper.result_id} paper={paper} aiDegraded={data.ai_degraded} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
