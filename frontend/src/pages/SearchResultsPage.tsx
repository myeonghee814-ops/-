import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { getSearch, searchPapers } from "../api/client";
import ErrorMessage from "../components/ErrorMessage";
import Loading from "../components/Loading";
import PaperCard from "../components/PaperCard";
import SearchBar from "../components/SearchBar";
import type { SearchResponse } from "../api/types";

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
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load search."))
      .finally(() => setLoading(false));
  }, [searchId]);

  async function handleNewSearch(keyword: string) {
    setSearching(true);
    setError(null);
    try {
      const response = await searchPapers(keyword);
      navigate(`/search/${response.search_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed. Please try again.");
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="results-page">
      <SearchBar initialValue={data?.keyword} loading={searching} onSubmit={handleNewSearch} />

      {loading && <Loading message="Loading results..." />}
      {error && <ErrorMessage message={error} />}

      {data && !loading && (
        <>
          <h2 className="results-heading">
            Top {data.results.length} papers for <span>&ldquo;{data.keyword}&rdquo;</span>
          </h2>
          <div className="paper-card-list">
            {data.results.map((paper) => (
              <PaperCard key={paper.result_id} paper={paper} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
