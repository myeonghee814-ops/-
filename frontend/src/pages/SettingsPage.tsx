import { FormEvent, useState } from "react";

import { clearApiKey, getApiKey, setApiKey } from "../lib/apiKey";

export default function SettingsPage() {
  const [key, setKey] = useState(() => getApiKey());
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setApiKey(key);
    setSavedMessage(key.trim() ? "저장되었습니다." : "키가 삭제되었습니다.");
  }

  function handleClear() {
    clearApiKey();
    setKey("");
    setSavedMessage("키가 삭제되었습니다.");
  }

  return (
    <div className="settings-page">
      <h1 className="settings-title">설정</h1>
      <p className="settings-subtitle">
        본인의 Gemini API 키를 입력하면 검색할 때 서버의 공용 키 대신 이 키를 사용합니다.
        "논문 검색"과 "논문 요약" 탭 모두 이 키를 공유해서 씁니다.
      </p>

      <form className="settings-form" onSubmit={handleSubmit}>
        <label className="settings-label" htmlFor="gemini-api-key">
          Gemini API 키
        </label>
        <input
          id="gemini-api-key"
          type="password"
          className="settings-input"
          placeholder="AIza..."
          value={key}
          onChange={(e) => {
            setKey(e.target.value);
            setSavedMessage(null);
          }}
          autoComplete="off"
        />
        <div className="settings-actions">
          <button type="submit" className="search-button">
            저장
          </button>
          <button type="button" className="back-link" onClick={handleClear}>
            키 삭제
          </button>
        </div>
        {savedMessage && <p className="settings-saved">{savedMessage}</p>}
      </form>

      <p className="settings-disclaimer">
        이 키는 브라우저에만 저장되며 서버 데이터베이스에는 저장되지 않습니다. 검색
        요청과 논문 요약(PDF 분석) 요청 모두 이 키가 함께 전달되어 각 요청의 AI
        호출에 사용됩니다. 키를 입력하지 않으면 검색은 서버에 설정된 공용 키로
        동작하고, 논문 요약은 키가 입력되기 전까지 비활성화됩니다.
      </p>
    </div>
  );
}
