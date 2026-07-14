import { Link } from "react-router-dom";

import type { PaperCard as PaperCardData } from "../api/types";
import BatterySnapshotView from "./BatterySnapshotView";
import RelevanceBadge from "./RelevanceBadge";

export default function PaperCard({ paper }: { paper: PaperCardData }) {
  return (
    <Link to={`/paper/${paper.result_id}`} className="paper-card">
      <div className="paper-card-header">
        <span className="paper-card-rank">#{paper.rank}</span>
        <RelevanceBadge score={paper.relevance_score} />
      </div>

      <h3 className="paper-card-title">{paper.title}</h3>
      <p className="paper-card-meta">
        {paper.authors} &middot; {paper.journal || "Unknown journal"}
        {paper.year ? ` · ${paper.year}` : ""}
      </p>
      {paper.doi && <p className="paper-card-doi">DOI: {paper.doi}</p>}

      <div className="paper-card-why">
        <span className="paper-card-why-label">Why this paper</span>
        <p>{paper.why_selected}</p>
      </div>

      <BatterySnapshotView snapshot={paper.battery_snapshot} />
    </Link>
  );
}
