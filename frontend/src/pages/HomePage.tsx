import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { searchPapers } from "../api/client";
import ErrorMessage from "../components/ErrorMessage";
import Loading from "../components/Loading";
import SearchBar from "../components/SearchBar";

export default function HomePage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(keyword: string) {
    setLoading(true);
    setError(null);
    try {
      const response = await searchPapers(keyword);
      navigate(`/search/${response.search_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed. Please try again.");
      setLoading(false);
    }
  }

  return (
    <div className="home-page">
      <h1 className="home-title">Find the right battery papers, not just the first ten.</h1>
      <p className="home-subtitle">
        Enter a keyword. BLIP searches the literature, then an AI re-ranks and analyzes
        results like a senior battery researcher would.
      </p>

      <SearchBar onSubmit={handleSearch} loading={loading} />

      {loading && (
        <Loading message="Searching literature and running AI relevance ranking... this can take up to a minute." />
      )}
      {error && <ErrorMessage message={error} />}
    </div>
  );
}
