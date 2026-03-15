import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function formatDateLabel(value) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "--";
  return parsed.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function getLineColor(latestScore) {
  if (latestScore >= 60) return "#dc2626";
  if (latestScore >= 30) return "#fbbf24";
  return "#34d399";
}

function DarkTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded border border-border bg-slate-900 px-3 py-2 text-xs text-slate-100">
      <p className="mb-1 text-slate-300">{formatDateLabel(label)}</p>
      <p>{`Risk score: ${payload[0].value}`}</p>
    </div>
  );
}

export default function RiskTrendChart({ history }) {
  if (history === null) {
    return (
      <section className="rounded-xl border border-border bg-surface p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-100">Risk Score Over Time</h2>
        <div className="mb-3 h-5 w-44 animate-pulse rounded bg-white/10" />
        <div className="h-56 animate-pulse rounded bg-white/5" />
      </section>
    );
  }

  if (!Array.isArray(history) || history.length === 0) {
    return (
      <section className="rounded-xl border border-border bg-surface p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-100">Risk Score Over Time</h2>
        <p className="text-xs text-slate-400">No risk history available.</p>
      </section>
    );
  }

  const normalized = history.map((point) => ({
    score: Number(point?.score) || 0,
    scored_at: point?.scored_at,
  }));
  const latestScore = normalized[normalized.length - 1]?.score ?? 0;
  const lineColor = getLineColor(latestScore);

  return (
    <section className="rounded-xl border border-border bg-surface p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-100">Risk Score Over Time</h2>
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={normalized}>
            <CartesianGrid stroke="rgba(148,163,184,0.12)" strokeDasharray="4 4" />
            <XAxis
              dataKey="scored_at"
              tickFormatter={formatDateLabel}
              stroke="rgba(203,213,225,0.7)"
              tick={{ fontSize: 11 }}
            />
            <YAxis
              domain={[0, 100]}
              stroke="rgba(203,213,225,0.7)"
              tick={{ fontSize: 11 }}
              tickCount={6}
            />
            <Tooltip content={<DarkTooltip />} />
            <ReferenceLine y={60} stroke="#dc2626" strokeDasharray="6 6" />
            <ReferenceLine y={30} stroke="#fbbf24" strokeDasharray="6 6" />
            <Line type="monotone" dataKey="score" stroke={lineColor} strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
