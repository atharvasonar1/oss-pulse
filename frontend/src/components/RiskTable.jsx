import ScoreBadge from "./ScoreBadge";

function formatTimestamp(value) {
  if (!value) return "N/A";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "N/A";
  return date.toLocaleString();
}

function getDeltaText(delta) {
  if (typeof delta !== "number" || Number.isNaN(delta)) return "0";
  const rounded = delta.toFixed(1);
  return delta > 0 ? `+${rounded}` : `${rounded}`;
}

export default function RiskTable({ projects, riskScores, onSelectProject }) {
  if (projects === null) {
    return (
      <div className="rounded-xl border border-border bg-surface p-4">
        <div className="mb-3 h-5 w-48 animate-pulse rounded bg-white/10" />
        <div className="space-y-2">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-10 animate-pulse rounded bg-white/5" />
          ))}
        </div>
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-surface p-8 text-center text-sm text-slate-300">
        No projects found.
      </div>
    );
  }

  const rows = projects
    .map((project) => {
      const risk = riskScores?.[project.id] || null;
      return {
        project,
        score: typeof risk?.score === "number" ? risk.score : 0,
        delta: typeof risk?.week_delta === "number" ? risk.week_delta : 0,
        topSignal: risk?.top_features?.[0]?.feature || "N/A",
        updatedAt: risk?.scored_at || null,
      };
    })
    .sort((a, b) => b.score - a.score);

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface">
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-xs sm:text-sm">
          <thead className="bg-white/5 text-slate-300">
            <tr>
              <th className="px-3 py-3">#</th>
              <th className="px-3 py-3">Project</th>
              <th className="px-3 py-3">Score</th>
              <th className="px-3 py-3">WoW Delta</th>
              <th className="px-3 py-3">Top Signal</th>
              <th className="px-3 py-3">Last Updated</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => {
              const critical = row.score >= 60;
              return (
                <tr
                  key={row.project.id}
                  className={`cursor-pointer border-t border-border transition hover:bg-white/5 ${
                    critical ? "border-l-4 border-l-risk-red" : ""
                  }`}
                  onClick={() => onSelectProject?.(row.project)}
                >
                  <td className="px-3 py-3 text-slate-400">{index + 1}</td>
                  <td className="px-3 py-3 font-medium">{`${row.project.owner}/${row.project.repo}`}</td>
                  <td className="px-3 py-3">
                    <ScoreBadge score={row.score} />
                  </td>
                  <td className="px-3 py-3">{getDeltaText(row.delta)}</td>
                  <td className="px-3 py-3">{row.topSignal}</td>
                  <td className="px-3 py-3 text-slate-400">{formatTimestamp(row.updatedAt)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
