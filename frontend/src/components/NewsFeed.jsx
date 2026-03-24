function getSentiment(score) {
  if (score > 0.1) return { label: "positive", className: "border-risk-green/60 bg-risk-green/10 text-risk-green" };
  if (score < -0.1) return { label: "negative", className: "border-risk-red/60 bg-risk-red/10 text-risk-red" };
  return { label: "neutral", className: "border-slate-500/60 bg-slate-500/10 text-slate-300" };
}

function formatPublished(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function isPlaceholderTitle(title) {
  const normalized = String(title || "").trim().toLowerCase();
  return normalized.startsWith("weekly update") && normalized.includes("for project");
}

export default function NewsFeed({ items }) {
  const news = Array.isArray(items) ? items : [];
  const realNews = news.filter((item) => !isPlaceholderTitle(item?.title)).slice(0, 8);

  return (
    <section className="rounded-xl border border-border bg-surface p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-100">Recent News</h2>

      {realNews.length === 0 ? (
        <p className="text-xs text-slate-400">No recent news articles found for this project</p>
      ) : (
        <ul className="max-h-80 space-y-2 overflow-y-auto pr-1">
          {realNews.map((item, index) => {
            const sentiment = getSentiment(Number(item?.sentiment_score) || 0);
            return (
              <li key={`${item?.url || "item"}-${index}`} className="rounded border border-border bg-white/5 p-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <a
                    href={item?.url || "#"}
                    target="_blank"
                    rel="noreferrer"
                    className="line-clamp-2 text-xs text-slate-100 hover:text-risk-yellow"
                  >
                    {item?.title || "Untitled article"}
                  </a>
                  <span className={`shrink-0 rounded border px-2 py-0.5 text-[10px] uppercase ${sentiment.className}`}>
                    {sentiment.label}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">{formatPublished(item?.published_at)}</p>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
