import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";

import App from "./App";
import "./styles/global.css";

// HashRouter (not BrowserRouter): the app is loaded via file:// once
// packaged (Electron) or previewed by double-clicking index.html, where
// the pathname is a filesystem path, not "/" - BrowserRouter can't match
// routes there. Hash-based routes (#/search/1) work identically under
// file://, http://, and in Electron.
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </React.StrictMode>,
);
