import type { KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";

import type { PaperCard as PaperCardData } from "../api/types";
import BatterySnapshotView from "./BatterySnapshotView";
import RelevanceBadge from "./RelevanceBadge";

/** DOI takes priority (the canonical, publisher-hosted link); a paper
 * without one still gets a usable external link via Semantic Scholar's own
 * page, keyed by the same paperId the search/rerank stages already use. */
function externalPaperUrl(paper: PaperCardData): string {
  return paper.doi
    ? `https://doi.org/${paper.doi}`
    : `https://www.semanticscholar.org/paper/${paper.external_paper_id}`;
}

export default function PaperCard({
  paper,
  aiDegraded = false,
}: {
  paper: PaperCardData;
  aiDegraded?: boolean;
}) {
  const navigate = useNavigate();

  // The whole card still navigates to the internal detail page on click,
  // same as before - but the title and "PDF 보기" are now real external
  // links (new tab), so they stop propagation to avoid also triggering
  // the card's own internal navigation.
  function goToDetail() {
    navigate(`/paper/${paper.result_id}`);
  }

  function handleCardKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      goToDetail();
    }
  }

  return (
    <div className="paper-card" role="link" tabIndex={0} onClick={goToDetail} onKeyDown={handleCardKeyDown}>
      <div className="paper-card-header">
        <span className="paper-card-rank">#{paper.rank}</span>
        {!aiDegraded && <RelevanceBadge score={paper.relevance_score} />}
      </div>

      <h3 className="paper-card-title">
        <a
          href={externalPaperUrl(paper)}
          target="_blank"
          rel="noopener noreferrer"
          className="paper-card-title-link"
          onClick={(e) => e.stopPropagation()}
        >
          {paper.title}
        </a>
      </h3>
      <p className="paper-card-meta">
        {paper.authors} &middot; {paper.journal || "저널 정보 없음"}
        {paper.year ? ` · ${paper.year}` : ""}
      </p>
      {paper.doi && <p className="paper-card-doi">DOI: {paper.doi}</p>}

      {paper.open_access_pdf_url && (
        <a
          href={paper.open_access_pdf_url}
          target="_blank"
          rel="noopener noreferrer"
          className="paper-card-pdf-link"
          onClick={(e) => e.stopPropagation()}
        >
          PDF 보기
        </a>
      )}

      {!aiDegraded && (
        <div className="paper-card-why">
          <span className="paper-card-why-label">AI 추천 이유</span>
          <p>{paper.why_selected}</p>
        </div>
      )}

      <BatterySnapshotView snapshot={paper.battery_snapshot} />
    </div>
  );
}
