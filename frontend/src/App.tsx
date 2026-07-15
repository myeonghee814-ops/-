import { Link, Route, Routes } from "react-router-dom";

import HomePage from "./pages/HomePage";
import PaperDetailPage from "./pages/PaperDetailPage";
import SearchResultsPage from "./pages/SearchResultsPage";
import SettingsPage from "./pages/SettingsPage";

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <Link to="/" className="brand">
          BLIP <span className="brand-sub">배터리 문헌 인텔리전스 플랫폼</span>
        </Link>
        <Link to="/settings" className="settings-link">
          설정
        </Link>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/search/:searchId" element={<SearchResultsPage />} />
          <Route path="/paper/:resultId" element={<PaperDetailPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
