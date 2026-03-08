import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import ContributorChart from "../components/ContributorChart";
import IssueChart from "../components/IssueChart";
import NewsFeed from "../components/NewsFeed";
import ScoreBadge from "../components/ScoreBadge";
import ShapExplainer from "../components/ShapExplainer";
import { fetchProjectByOwnerRepo, fetchRiskScore, fetchSnapshots } from "../lib/api";

function normalizeNewsItems(snapshots) {
  if (!Array.isArray(snapshots)) return [];

  const items = snapshots.flatMap((snapshot) => (Array.isArray(snapshot?.news_items) ? snapshot.news_items : []));

  return items
    .map((item) => ({
      title: item?.title,
      url: item?.url,
      sentiment_score: Number(item?.sentiment_score) || 0,
      published_at: item?.published_at,
    }))
    .filter((item) => item.title && item.url)
    .sort((a, b) => new Date(b.published_at).getTime() - new Date(a.published_at).getTime());
}

function getOpenIssuesCount(snapshots) {
  if (!Array.isArray(snapshots) || snapshots.length === 0) return "N/A";
  const latest = snapshots[snapshots.length - 1];
  return typeof latest?.open_issues === "number" ? latest.open_issues : "N/A";
}

export default function ProjectDetail() {
  const navigate = useNavigate();
  const { owner, repo } = useParams();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notFound, setNotFound] = useState(false);
  const [project, setProject] = useState(null);
  const [riskScore, setRiskScore] = useState(null);
  const [snapshots, setSnapshots] = useState(null);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError("");
      setNotFound(false);
      setProject(null);
      setRiskScore(null);
      setSnapshots(null);

      const projectResp = await fetchProjectByOwnerRepo(owner, repo);
      if (!active) return;

      if (!projectResp.ok) {
        setError(projectResp.error || "Failed to load project");
        setLoading(false);
        return;
      }

      if (!projectResp.data) {
        setNotFound(true);
        setLoading(false);
        return;
      }

      setProject(projectResp.data);

      const [riskResp, snapshotsResp] = await Promise.all([
        fetchRiskScore(projectResp.data.id),
        fetchSnapshots(projectResp.data.id),
      ]);

      if (!active) return;

      if (riskResp.ok) {
        setRiskScore(riskResp.data);
      }

      if (snapshotsResp.ok && Array.isArray(snapshotsResp.data)) {
        setSnapshots(snapshotsResp.data);
      } else {
        setSnapshots([]);
      }

      if (!riskResp.ok && !snapshotsResp.ok) {
        setError("Failed to load project telemetry");
      }

      setLoading(false);
    }

    load();

    return () => {
      active = false;
    };
  }, [owner, repo]);

  const newsItems = useMemo(() => normalizeNewsItems(snapshots), [snapshots]);

  const metadata = useMemo(
    () => ({
      stars: project?.stargazers_count ?? "N/A",
      forks: project?.forks_count ?? "N/A",
      openIssues: getOpenIssuesCount(snapshots),
    }),
    [project, snapshots]
  );

  if (loading) {
    return (
      <main className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8">
        <div className="mb-4 h-8 w-52 animate-pulse rounded bg-white/10" />
        <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <div className="space-y-4">
            <ContributorChart snapshots={null} />
            <IssueChart snapshots={null} />
          </div>
          <div className="space-y-4">
            <div className="h-24 animate-pulse rounded-xl border border-border bg-surface" />
            <div className="h-64 animate-pulse rounded-xl border border-border bg-surface" />
          </div>
        </div>
      </main>
    );
  }

  if (notFound) {
    return (
      <main className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8">
        <button onClick={() => navigate("/")} className="mb-4 rounded border border-border px-3 py-1 text-xs hover:bg-white/5">
          ← Back
        </button>
        <div className="rounded-xl border border-border bg-surface p-6 text-sm text-slate-300">Project not found.</div>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <button
          onClick={() => navigate("/")}
          className="rounded border border-border px-3 py-1 text-xs text-slate-200 transition hover:bg-white/5"
        >
          ← Back
        </button>
        <h1 className="text-lg font-semibold text-slate-100">{`${owner}/${repo}`}</h1>
      </div>

      {error ? (
        <div className="mb-4 rounded-xl border border-risk-red/40 bg-risk-red/10 p-3 text-xs text-red-200">{error}</div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-4">
          <ContributorChart snapshots={snapshots} />
          <IssueChart snapshots={snapshots} />
          <NewsFeed items={newsItems} />
        </div>

        <aside className="space-y-4">
          <section className="rounded-xl border border-border bg-surface p-4">
            <p className="mb-2 text-xs text-slate-400">Current Risk Score</p>
            <div className="scale-125 origin-left">
              <ScoreBadge score={riskScore?.score ?? 0} />
            </div>
          </section>

          <ShapExplainer topFeatures={riskScore?.top_features || []} />

          <section className="rounded-xl border border-border bg-surface p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-100">Metadata</h2>
            <dl className="space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <dt className="text-slate-400">Stars</dt>
                <dd className="text-slate-200">{metadata.stars}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-slate-400">Forks</dt>
                <dd className="text-slate-200">{metadata.forks}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-slate-400">Open Issues</dt>
                <dd className="text-slate-200">{metadata.openIssues}</dd>
              </div>
            </dl>
          </section>
        </aside>
      </div>
    </main>
  );
}
