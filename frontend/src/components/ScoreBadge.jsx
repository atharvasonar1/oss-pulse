function getScoreStyles(score) {
  if (score >= 60) {
    return "border-risk-red/70 bg-risk-red/10 text-risk-red";
  }
  if (score >= 30) {
    return "border-risk-yellow/70 bg-risk-yellow/10 text-risk-yellow";
  }
  return "border-risk-green/70 bg-risk-green/10 text-risk-green";
}

function getRingColor(score) {
  if (score >= 60) return "#dc2626";
  if (score >= 30) return "#fbbf24";
  return "#34d399";
}

export default function ScoreBadge({ score, variant = "badge" }) {
  const safeScore = Number.isFinite(score) ? Math.round(score) : 0;

  if (variant === "ring") {
    const radius = 32;
    const strokeWidth = 5;
    const normalized = Math.max(0, Math.min(100, safeScore));
    const circumference = 2 * Math.PI * radius;
    const dashOffset = circumference - (normalized / 100) * circumference;
    const ringColor = getRingColor(safeScore);

    return (
      <div className="relative inline-flex h-20 w-20 items-center justify-center">
        <svg viewBox="0 0 80 80" className="h-20 w-20 -rotate-90" data-testid="score-ring-svg" aria-hidden="true">
          <circle cx="40" cy="40" r={radius} fill="none" stroke="rgba(148,163,184,0.25)" strokeWidth={strokeWidth} />
          <circle
            cx="40"
            cy="40"
            r={radius}
            fill="none"
            stroke={ringColor}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
          />
        </svg>
        <span className="absolute text-xl font-semibold text-slate-100">{normalized}</span>
      </div>
    );
  }

  return (
    <span
      className={`inline-flex min-w-14 items-center justify-center rounded border px-2 py-1 text-xs font-semibold tracking-wide ${getScoreStyles(
        safeScore
      )}`}
    >
      {safeScore}
    </span>
  );
}
