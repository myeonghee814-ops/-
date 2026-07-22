import { Link, Route, Routes, useLocation } from "react-router-dom";

import HomePage from "./pages/HomePage";
import PaperDetailPage from "./pages/PaperDetailPage";
import SearchResultsPage from "./pages/SearchResultsPage";
import SettingsPage from "./pages/SettingsPage";
import SummarizerPage from "./pages/SummarizerPage";

export default function App() {
  const location = useLocation();
  const isSummarizerTab = location.pathname.startsWith("/summarizer");

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-left">
          <Link to="/" className="brand">
            BLIP <span className="brand-sub">배터리 문헌 인텔리전스 플랫폼</span>
          </Link>
          <nav className="tab-bar">
            <Link to="/" className={`tab-link ${!isSummarizerTab ? "tab-link-active" : ""}`}>
              논문 검색
            </Link>
            <Link to="/summarizer" className={`tab-link ${isSummarizerTab ? "tab-link-active" : ""}`}>
              논문 요약
            </Link>
          </nav>
        </div>
        <Link to="/settings" className="settings-link">
          설정
        </Link>
      </header>
      {/* The summarizer tab owns its own full-width sidebar+content layout
          (ported from battery-paper-summarizer as-is) - it needs the full
          viewport width, unlike the other pages which stay in the centered
          960px reading column. */}
      <main className={isSummarizerTab ? "app-main-full" : "app-main"}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/search/:searchId" element={<SearchResultsPage />} />
          <Route path="/paper/:resultId" element={<PaperDetailPage />} />
          <Route path="/summarizer" element={<SummarizerPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
