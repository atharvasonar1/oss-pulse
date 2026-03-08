function getScoreStyles(score) {
  if (score >= 60) {
    return "border-risk-red/70 bg-risk-red/10 text-risk-red";
  }
  if (score >= 30) {
    return "border-risk-yellow/70 bg-risk-yellow/10 text-risk-yellow";
  }
  return "border-risk-green/70 bg-risk-green/10 text-risk-green";
}

export default function ScoreBadge({ score }) {
  const safeScore = Number.isFinite(score) ? Math.round(score) : 0;
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
