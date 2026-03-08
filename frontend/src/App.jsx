import { BrowserRouter, Route, Routes } from "react-router-dom";

import Overview from "./pages/Overview";
import ProjectDetail from "./pages/ProjectDetail";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-[radial-gradient(circle_at_20%_0%,rgba(30,41,59,0.45),transparent_40%),radial-gradient(circle_at_80%_0%,rgba(15,23,42,0.8),transparent_55%),#080c14]">
        <header className="border-b border-border bg-surface/60 backdrop-blur">
          <div className="mx-auto flex w-full max-w-7xl items-center justify-between p-4 sm:p-6">
            <div className="flex items-center gap-3">
              <div className="h-3 w-3 rounded-full bg-risk-red shadow-[0_0_16px_rgba(220,38,38,0.9)]" />
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">OSS Pulse</p>
                <h1 className="text-lg font-semibold text-slate-100">Dependency Health Monitor</h1>
              </div>
            </div>
            <div className="inline-flex items-center gap-2 rounded-full border border-risk-green/40 bg-risk-green/10 px-3 py-1 text-xs text-risk-green">
              <span className="h-2 w-2 rounded-full bg-risk-green" />
              Live
            </div>
          </div>
        </header>

        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/project/:owner/:repo" element={<ProjectDetail />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
