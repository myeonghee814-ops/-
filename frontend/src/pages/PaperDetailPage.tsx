import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { getPaperDetail } from "../api/client";
import BatterySnapshotView from "../components/BatterySnapshotView";
import ErrorMessage from "../components/ErrorMessage";
import Loading from "../components/Loading";
import RelevanceBadge from "../components/RelevanceBadge";
import type { PaperDetail } from "../api/types";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="detail-section">
      <h3>{title}</h3>
      <p>{children}</p>
    </section>
  );
}

export default function PaperDetailPage() {
  const { resultId } = useParams<{ resultId: string }>();
  const navigate = useNavigate();
  const [paper, setPaper] = useState<PaperDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!resultId) return;
    setLoading(true);
    setError(null);
    getPaperDetail(resultId)
      .then(setPaper)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load paper."))
      .finally(() => setLoading(false));
  }, [resultId]);

  if (loading) return <Loading message="Loading paper details..." />;
  if (error) return <ErrorMessage message={error} />;
  if (!paper) return null;

  return (
    <div className="detail-page">
      <button type="button" className="back-link" onClick={() => navigate(-1)}>
        &larr; Back to results
      </button>

      <div className="detail-header">
        <RelevanceBadge score={paper.relevance_score} />
        <h1>{paper.title}</h1>
        <p className="detail-meta">
          {paper.authors} &middot; {paper.journal || "Unknown journal"}
          {paper.year ? ` · ${paper.year}` : ""}
        </p>
      </div>

      <section className="detail-section detail-why">
        <h3>Why this paper</h3>
        <p>{paper.why_selected}</p>
      </section>

      <section className="detail-section">
        <h3>Battery Snapshot</h3>
        <BatterySnapshotView snapshot={paper.battery_snapshot} />
      </section>

      <Section title="Experimental Conditions">{paper.experimental_conditions}</Section>
      <Section title="Performance Summary">{paper.performance_summary}</Section>
      <Section title="Innovation">{paper.innovation}</Section>
      <Section title="Advantages">{paper.advantages}</Section>
      <Section title="Limitations">{paper.limitations}</Section>
      <Section title="Abstract">{paper.abstract}</Section>

      <section className="detail-section">
        <h3>Metadata</h3>
        <ul className="detail-metadata-list">
          <li>
            <strong>Search keyword:</strong> {paper.keyword}
          </li>
          <li>
            <strong>Journal:</strong> {paper.journal || "Unknown"}
          </li>
          <li>
            <strong>Year:</strong> {paper.year ?? "Unknown"}
          </li>
          <li>
            <strong>DOI:</strong> {paper.doi || "Not available"}
          </li>
        </ul>
      </section>
    </div>
  );
}
