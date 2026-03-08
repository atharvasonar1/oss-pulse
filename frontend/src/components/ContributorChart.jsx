import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function formatWeekLabel(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function DarkTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded border border-border bg-slate-900 px-3 py-2 text-xs text-slate-100">
      <p className="mb-1 text-slate-300">{formatWeekLabel(label)}</p>
      <p>{`Contributors: ${payload[0].value}`}</p>
    </div>
  );
}

export default function ContributorChart({ snapshots }) {
  if (snapshots === null) {
    return (
      <section className="rounded-xl border border-border bg-surface p-4">
        <div className="mb-3 h-5 w-40 animate-pulse rounded bg-white/10" />
        <div className="h-64 animate-pulse rounded bg-white/5" />
      </section>
    );
  }

  if (!Array.isArray(snapshots) || snapshots.length === 0) {
    return (
      <section className="rounded-xl border border-border bg-surface p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-100">Contributors Over Time</h2>
        <p className="text-xs text-slate-400">No snapshot history available.</p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-border bg-surface p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-100">Contributors Over Time</h2>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={snapshots}>
            <CartesianGrid stroke="rgba(148,163,184,0.12)" strokeDasharray="4 4" />
            <XAxis
              dataKey="week"
              tickFormatter={formatWeekLabel}
              stroke="rgba(203,213,225,0.7)"
              tick={{ fontSize: 11 }}
            />
            <YAxis stroke="rgba(203,213,225,0.7)" tick={{ fontSize: 11 }} />
            <Tooltip content={<DarkTooltip />} />
            <Area
              type="monotone"
              dataKey="contributor_count"
              stroke="#34d399"
              strokeWidth={2}
              fill="rgba(52,211,153,0.15)"
              fillOpacity={1}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
