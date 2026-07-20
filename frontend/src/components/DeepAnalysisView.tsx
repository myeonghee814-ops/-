import type { DeepAnalysis } from "../api/types";

export default function DeepAnalysisView({ analysis }: { analysis: DeepAnalysis }) {
  const fields: [string, string][] = [
    ["베이스 전해액", analysis.base_electrolyte],
    ["실험 전해액", analysis.test_electrolyte],
    ["전압 범위", analysis.voltage_range],
    ["전지 형태", analysis.cell_type_detail],
  ];

  return (
    <div className="deep-analysis-results">
      <div className="battery-snapshot">
        {fields.map(([label, value]) => (
          <div className="battery-snapshot-field" key={label}>
            <span className="battery-snapshot-label">{label}</span>
            <span className="battery-snapshot-value">{value || "정보 없음"}</span>
          </div>
        ))}
      </div>
      <p className="deep-analysis-text">
        <strong>핵심 결과:</strong> {analysis.key_findings || "정보 없음"}
      </p>
      <p className="deep-analysis-text">
        <strong>종합 요약:</strong> {analysis.summary || "정보 없음"}
      </p>
    </div>
  );
}
