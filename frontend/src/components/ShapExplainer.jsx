function formatFeatureName(name) {
  if (!name) return "Unknown signal";
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export default function ShapExplainer({ topFeatures }) {
  const features = Array.isArray(topFeatures) ? topFeatures.slice(0, 3) : [];

  if (features.length === 0) {
    return (
      <section className="rounded-xl border border-border bg-surface p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-100">Why this score?</h2>
        <p className="text-xs text-slate-400">No feature explanations available yet.</p>
      </section>
    );
  }

  const maxAbs = Math.max(...features.map((feature) => Math.abs(Number(feature?.shap_value) || 0)), 1);

  return (
    <section className="rounded-xl border border-border bg-surface p-4">
      <h2 className="mb-4 text-sm font-semibold text-slate-100">Why this score?</h2>
      <div className="space-y-3">
        {features.map((feature, index) => {
          const shapValue = Number(feature?.shap_value) || 0;
          const widthPct = Math.max(8, (Math.abs(shapValue) / maxAbs) * 100);
          const isRisk = feature?.direction === "risk";
          return (
            <div key={`${feature?.feature || "unknown"}-${index}`} className="space-y-1">
              <div className="flex items-center justify-between gap-3 text-xs">
                <span className="truncate text-slate-200">{formatFeatureName(feature?.feature)}</span>
                <span
                  className={`rounded border px-2 py-0.5 ${
                    isRisk
                      ? "border-risk-red/60 bg-risk-red/10 text-risk-red"
                      : "border-risk-green/60 bg-risk-green/10 text-risk-green"
                  }`}
                >
                  {isRisk ? "↑ risk" : "↓ safe"}
                </span>
              </div>
              <div className="h-2 rounded bg-white/10">
                <div
                  className={`h-2 rounded ${isRisk ? "bg-risk-red/80" : "bg-risk-green/80"}`}
                  style={{ width: `${widthPct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
