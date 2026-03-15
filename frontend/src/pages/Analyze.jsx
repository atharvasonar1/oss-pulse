import { useState } from "react";

import ScoreBadge from "../components/ScoreBadge";
import { analyzeManifest } from "../lib/api";


export default function Analyze() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const onFileChange = (event) => {
    const selected = event.target.files?.[0] || null;
    setFile(selected);
    setError("");
    setResult(null);
  };

  const onAnalyze = async () => {
    if (!file) return;
    setLoading(true);
    setError("");
    setResult(null);

    const response = await analyzeManifest(file);
    if (response.ok) {
      setResult(response.data || { matched: [], unmatched: [] });
    } else {
      setError(response.error || "Manifest analysis failed");
    }
    setLoading(false);
  };

  return (
    <main className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8">
      <section className="mb-6 rounded-xl border border-border bg-surface p-4">
        <h1 className="mb-2 text-lg font-semibold text-slate-100">Analyze Dependency Manifest</h1>
        <p className="text-xs text-slate-400">Upload requirements.txt, package.json, or go.mod to map packages to monitored risk scores.</p>
      </section>

      <section className="mb-6 rounded-xl border border-border bg-surface p-4">
        <label htmlFor="manifest-file" className="mb-3 block text-sm font-medium text-slate-200">
          Upload dependency manifest
        </label>
        <input
          id="manifest-file"
          type="file"
          accept=".txt,.json,.mod"
          onChange={onFileChange}
          className="block w-full rounded border border-border bg-white/5 p-2 text-xs text-slate-200"
        />
        <p className="mt-2 text-xs text-slate-400">{file ? `Selected: ${file.name}` : "No file selected yet."}</p>
        <button
          type="button"
          disabled={!file || loading}
          onClick={onAnalyze}
          className="mt-3 rounded border border-border px-3 py-1 text-xs text-slate-100 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Analyzing..." : "Analyze"}
        </button>
      </section>

      {error ? (
        <div className="mb-4 rounded-xl border border-risk-red/50 bg-risk-red/10 p-3 text-sm text-red-200">{error}</div>
      ) : null}

      {!result ? (
        <section className="rounded-xl border border-border bg-surface p-6 text-sm text-slate-300">
          Upload a manifest to see matched and unmatched dependencies.
        </section>
      ) : (
        <div className="space-y-4">
          <section className="rounded-xl border border-border bg-surface p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-100">Matched Packages</h2>
            {result.matched?.length ? (
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-xs sm:text-sm">
                  <thead className="text-slate-300">
                    <tr>
                      <th className="px-2 py-2">Package</th>
                      <th className="px-2 py-2">Repo</th>
                      <th className="px-2 py-2">Risk Score</th>
                      <th className="px-2 py-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.matched.map((row, idx) => (
                      <tr key={`${row.package}-${idx}`} className="border-t border-border">
                        <td className="px-2 py-2">{row.package}</td>
                        <td className="px-2 py-2">{`${row.owner}/${row.repo}`}</td>
                        <td className="px-2 py-2">
                          {typeof row.score === "number" ? <ScoreBadge score={row.score} /> : <span className="text-slate-400">N/A</span>}
                        </td>
                        <td className="px-2 py-2 text-risk-green">Monitored</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-slate-400">No monitored package matches found.</p>
            )}
          </section>

          <section className="rounded-xl border border-border bg-surface p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-100">Unmatched Packages</h2>
            {result.unmatched?.length ? (
              <ul className="space-y-2 text-xs">
                {result.unmatched.map((name) => (
                  <li key={name} className="flex items-center justify-between rounded border border-border bg-white/5 px-2 py-2">
                    <span>{name}</span>
                    <span className="rounded border border-slate-500/60 bg-slate-500/10 px-2 py-0.5 text-[10px] uppercase text-slate-300">
                      Not monitored
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-400">All packages matched monitored repositories.</p>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
