import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { searchPapers } from "../api/client";
import ErrorMessage from "../components/ErrorMessage";
import Loading from "../components/Loading";
import SearchBar from "../components/SearchBar";
import type { SearchRequest } from "../api/types";

export default function HomePage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(request: SearchRequest) {
    setLoading(true);
    setError(null);
    try {
      const response = await searchPapers(request);
      navigate(`/search/${response.search_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "검색에 실패했습니다. 다시 시도해주세요.");
      setLoading(false);
    }
  }

  return (
    <div className="home-page">
      <h1 className="home-title">가장 관련성 높은 배터리 논문을 찾아드립니다.</h1>
      <p className="home-subtitle">
        소재는 한글 또는 영어로 입력하세요. BLIP이 문헌을 검색하고, AI가 배터리
        연구자처럼 논문을 재순위화하고 분석합니다.
      </p>

      <SearchBar onSubmit={handleSearch} loading={loading} />

      {loading && (
        <Loading message="문헌을 검색하고 AI 관련도 분석을 실행하는 중입니다... 최대 2분 정도 걸릴 수 있습니다." />
      )}
      {error && <ErrorMessage message={error} />}
    </div>
  );
}
