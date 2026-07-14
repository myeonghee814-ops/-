export default function RelevanceBadge({ score }: { score: number }) {
  const rounded = Math.round(score);
  const tier = rounded >= 80 ? "high" : rounded >= 60 ? "medium" : "low";

  return (
    <div className={`relevance-badge relevance-badge--${tier}`} title="AI relevance score">
      <span className="relevance-badge-score">{rounded}</span>
      <span className="relevance-badge-max">/100</span>
    </div>
  );
}
