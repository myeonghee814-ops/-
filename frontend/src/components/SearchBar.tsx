import { FormEvent, useEffect, useState } from "react";

import type { SearchRequest, SortBy } from "../api/types";

interface SearchBarProps {
  initialValue?: SearchRequest;
  loading?: boolean;
  onSubmit: (request: SearchRequest) => void;
}

const MATERIAL_EXAMPLES = ["NCA811", "실리콘 음극", "LFP", "리튬 금속 음극"];

const SORT_OPTIONS: { value: SortBy; label: string; description: string }[] = [
  { value: "relevance", label: "정확도 우선", description: "관련성 점수를 우선 정렬, 동점이면 최신순" },
  { value: "recency", label: "최신순 우선", description: "발행 연도를 우선 정렬, 동점이면 관련성순" },
];

const PERFORMANCE_CHIPS = [
  "사이클 수명",
  "율속 특성",
  "쿨롱 효율",
  "용량 유지율",
  "저온 성능",
  "안전성",
];

function toChipList(value: string): string[] {
  return value
    .split(/\s*,\s*/)
    .map((part) => part.trim())
    .filter(Boolean);
}

export default function SearchBar({ initialValue, loading = false, onSubmit }: SearchBarProps) {
  const [material, setMaterial] = useState(initialValue?.material ?? "");
  const [performance, setPerformance] = useState(initialValue?.performance ?? "");
  const [additiveOrSolvent, setAdditiveOrSolvent] = useState(initialValue?.additive_or_solvent ?? "");
  const [sortBy, setSortBy] = useState<SortBy>(initialValue?.sort_by ?? "relevance");

  useEffect(() => {
    if (!initialValue) return;
    setMaterial(initialValue.material);
    setPerformance(initialValue.performance);
    setAdditiveOrSolvent(initialValue.additive_or_solvent);
    setSortBy(initialValue.sort_by);
  }, [initialValue]);

  const trimmedMaterial = material.trim();
  const canSubmit = !loading && trimmedMaterial.length > 0;

  function submit() {
    if (!canSubmit) return;
    onSubmit({
      material: trimmedMaterial,
      performance: performance.trim(),
      additive_or_solvent: additiveOrSolvent.trim(),
      sort_by: sortBy,
    });
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    submit();
  }

  function togglePerformanceChip(term: string) {
    const chips = toChipList(performance);
    const next = chips.includes(term) ? chips.filter((chip) => chip !== term) : [...chips, term];
    setPerformance(next.join(", "));
  }

  const activePerformanceChips = new Set(toChipList(performance));

  return (
    <form className="search-form" onSubmit={handleSubmit}>
      <div className="search-field">
        <label className="search-field-label" htmlFor="search-material">
          소재 <span className="search-field-required">필수</span>
        </label>
        <input
          id="search-material"
          type="text"
          className="search-input"
          placeholder="예: NCA811, 실리콘 음극"
          value={material}
          onChange={(e) => setMaterial(e.target.value)}
          disabled={loading}
          autoFocus
        />
        <div className="search-field-chips">
          {MATERIAL_EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              className="example-chip"
              disabled={loading}
              onClick={() => setMaterial(example)}
            >
              {example}
            </button>
          ))}
        </div>
      </div>

      <div className="search-field">
        <label className="search-field-label" htmlFor="search-performance">
          성능/특성 <span className="search-field-optional">선택</span>
        </label>
        <input
          id="search-performance"
          type="text"
          className="search-input"
          placeholder="예: 사이클 수명, 저온 성능"
          value={performance}
          onChange={(e) => setPerformance(e.target.value)}
          disabled={loading}
        />
        <div className="search-field-chips">
          {PERFORMANCE_CHIPS.map((chip) => (
            <button
              key={chip}
              type="button"
              className={`example-chip${activePerformanceChips.has(chip) ? " example-chip-active" : ""}`}
              disabled={loading}
              onClick={() => togglePerformanceChip(chip)}
            >
              {chip}
            </button>
          ))}
        </div>
      </div>

      <div className="search-field">
        <label className="search-field-label" htmlFor="search-additive">
          첨가제 또는 용매 <span className="search-field-optional">선택</span>
        </label>
        <input
          id="search-additive"
          type="text"
          className="search-input"
          placeholder="예: FEC, LiFSI"
          value={additiveOrSolvent}
          onChange={(e) => setAdditiveOrSolvent(e.target.value)}
          disabled={loading}
        />
      </div>

      <div className="search-field">
        <span className="search-field-label">정렬 기준</span>
        <div className="sort-toggle" role="radiogroup" aria-label="정렬 기준">
          {SORT_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={sortBy === option.value}
              title={option.description}
              className={`sort-toggle-option${sortBy === option.value ? " sort-toggle-option-active" : ""}`}
              disabled={loading}
              onClick={() => setSortBy(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <button type="submit" className="search-button" disabled={!canSubmit}>
        {loading ? "검색 중..." : "검색"}
      </button>
    </form>
  );
}
