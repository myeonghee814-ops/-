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
      .catch((err) => setError(err instanceof Error ? err.message : "논문 정보를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, [resultId]);

  if (loading) return <Loading message="논문 상세 정보를 불러오는 중입니다..." />;
  if (error) return <ErrorMessage message={error} />;
  if (!paper) return null;

  return (
    <div className="detail-page">
      <button type="button" className="back-link" onClick={() => navigate(-1)}>
        &larr; 결과로 돌아가기
      </button>

      <div className="detail-header">
        <RelevanceBadge score={paper.relevance_score} />
        <h1>{paper.title}</h1>
        <p className="detail-meta">
          {paper.authors} &middot; {paper.journal || "저널 정보 없음"}
          {paper.year ? ` · ${paper.year}` : ""}
        </p>
      </div>

      <section className="detail-section detail-why">
        <h3>AI 추천 이유</h3>
        <p>{paper.why_selected}</p>
      </section>

      <section className="detail-section">
        <h3>배터리 정보</h3>
        <BatterySnapshotView snapshot={paper.battery_snapshot} />
      </section>

      <Section title="실험 조건">{paper.experimental_conditions}</Section>
      <Section title="주요 성능">{paper.performance_summary}</Section>
      <Section title="혁신 포인트">{paper.innovation}</Section>
      <Section title="장점">{paper.advantages}</Section>
      <Section title="한계">{paper.limitations}</Section>
      <Section title="초록">{paper.abstract}</Section>

      <section className="detail-section">
        <h3>메타데이터</h3>
        <ul className="detail-metadata-list">
          <li>
            <strong>검색 키워드:</strong> {paper.keyword}
          </li>
          <li>
            <strong>저널:</strong> {paper.journal || "정보 없음"}
          </li>
          <li>
            <strong>발행연도:</strong> {paper.year ?? "정보 없음"}
          </li>
          <li>
            <strong>DOI:</strong> {paper.doi || "확인 불가"}
          </li>
        </ul>
      </section>
    </div>
  );
}
