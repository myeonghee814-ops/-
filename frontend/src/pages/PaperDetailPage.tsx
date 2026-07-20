import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { getPaperDetail, runDeepAnalysis } from "../api/client";
import BatterySnapshotView from "../components/BatterySnapshotView";
import DeepAnalysisView from "../components/DeepAnalysisView";
import ErrorMessage from "../components/ErrorMessage";
import InfoMessage from "../components/InfoMessage";
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
  const [deepAnalyzing, setDeepAnalyzing] = useState(false);
  const [deepAnalysisError, setDeepAnalysisError] = useState<string | null>(null);

  useEffect(() => {
    if (!resultId) return;
    setLoading(true);
    setError(null);
    getPaperDetail(resultId)
      .then(setPaper)
      .catch((err) => setError(err instanceof Error ? err.message : "논문 정보를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, [resultId]);

  async function handleDeepAnalysis() {
    if (!resultId) return;
    setDeepAnalyzing(true);
    setDeepAnalysisError(null);
    try {
      setPaper(await runDeepAnalysis(resultId));
    } catch (err) {
      setDeepAnalysisError(err instanceof Error ? err.message : "심층 분석에 실패했습니다.");
    } finally {
      setDeepAnalyzing(false);
    }
  }

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

      <section className="detail-section deep-analysis-section">
        <h3>심층 분석 (원문 PDF 기반)</h3>
        {paper.deep_analysis ? (
          <DeepAnalysisView analysis={paper.deep_analysis} />
        ) : paper.open_access_pdf_url ? (
          <>
            <p className="deep-analysis-hint">
              초록만으로는 전해액 조성, 전압 범위 같은 세부 실험 조건을 파악하기 어려운 경우가
              많습니다. 이 논문은 원문 PDF가 공개되어 있어, 원문을 직접 분석해 더 정확한 실험
              조건을 확인할 수 있습니다.
            </p>
            <button
              type="button"
              className="deep-analysis-button"
              onClick={handleDeepAnalysis}
              disabled={deepAnalyzing}
            >
              {deepAnalyzing ? "분석 중..." : "자세히 분석"}
            </button>
            {deepAnalyzing && (
              <Loading message="원문 PDF를 다운로드하고 분석하는 중입니다... (최대 1~2분 소요)" />
            )}
            {deepAnalysisError && <ErrorMessage message={deepAnalysisError} />}
          </>
        ) : (
          <InfoMessage message="원문 접근 불가 - 초록 기반 요약만 제공됩니다." />
        )}
      </section>

      <Section title="실험 조건">{paper.experimental_conditions}</Section>
      <Section title="핵심 실험 결과 요약">{paper.result_summary}</Section>
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
