import { FormEvent, useState } from "react";

interface SearchBarProps {
  initialValue?: string;
  loading?: boolean;
  onSubmit: (keyword: string) => void;
}

const EXAMPLE_KEYWORDS = [
  "NCA 전해액 첨가제",
  "실리콘 음극 SEI",
  "LiFSI 고농도 전해질",
  "하이니켈 양극 사이클 안정성",
];

export default function SearchBar({ initialValue = "", loading = false, onSubmit }: SearchBarProps) {
  const [keyword, setKeyword] = useState(initialValue);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = keyword.trim();
    if (trimmed.length >= 2) {
      onSubmit(trimmed);
    }
  }

  return (
    <div className="search-bar-wrapper">
      <form className="search-bar" onSubmit={handleSubmit}>
        <input
          type="text"
          className="search-input"
          placeholder="예: NCA 전해액 첨가제"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          disabled={loading}
          autoFocus
        />
        <button type="submit" className="search-button" disabled={loading || keyword.trim().length < 2}>
          {loading ? "검색 중..." : "검색"}
        </button>
      </form>
      <div className="example-keywords">
        {EXAMPLE_KEYWORDS.map((example) => (
          <button
            key={example}
            type="button"
            className="example-chip"
            disabled={loading}
            onClick={() => {
              setKeyword(example);
              onSubmit(example);
            }}
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}
