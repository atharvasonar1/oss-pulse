import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import RiskTable from "../components/RiskTable";
import { fetchProjects, fetchRiskScore } from "../lib/api";

function getLastUpdated(riskScores) {
  const dates = Object.values(riskScores || {})
    .map((item) => new Date(item?.scored_at || 0))
    .filter((date) => !Number.isNaN(date.getTime()));

  if (dates.length === 0) return "N/A";
  const latest = dates.reduce((max, current) => (current > max ? current : max));
  return latest.toLocaleString();
}

export default function Overview() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState(null);
  const [riskScores, setRiskScores] = useState({});
  const [loading, setLoading] = useState(true);
  const [isRiskLoading, setIsRiskLoading] = useState(false);
  const [error, setError] = useState("");
  const [animatedStats, setAnimatedStats] = useState({ monitored: 0, avg: 0, critical: 0 });

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError("");

      const projectsResp = await fetchProjects();
      if (!active) return;

      if (!projectsResp.ok) {
        setProjects([]);
        setRiskScores({});
        setError(projectsResp.error || "Failed to load projects");
        setLoading(false);
        return;
      }

      const loadedProjects = Array.isArray(projectsResp.data) ? projectsResp.data : [];
      setProjects(loadedProjects);
      setLoading(false);

      if (loadedProjects.length === 0) {
        setRiskScores({});
        setIsRiskLoading(false);
        return;
      }

      setIsRiskLoading(true);
      const scoreEntries = await Promise.all(
        loadedProjects.map(async (project) => {
          const scoreResp = await fetchRiskScore(project.id);
          return [project.id, scoreResp.ok ? scoreResp.data : null];
        })
      );

      if (!active) return;
      setRiskScores(Object.fromEntries(scoreEntries));
      setIsRiskLoading(false);
    }

    load();

    return () => {
      active = false;
    };
  }, []);

  const stats = useMemo(() => {
    const scores = Object.values(riskScores)
      .map((item) => item?.score)
      .filter((value) => typeof value === "number");

    const monitored = Array.isArray(projects) ? projects.length : 0;
    const avg = scores.length ? scores.reduce((sum, value) => sum + value, 0) / scores.length : 0;
    const critical = scores.filter((score) => score >= 60).length;

    return {
      monitored,
      avg,
      critical,
      updated: getLastUpdated(riskScores),
    };
  }, [projects, riskScores]);

  useEffect(() => {
    const targetMonitored = Number.isFinite(stats.monitored) ? stats.monitored : 0;
    const targetAvg = Number.isFinite(stats.avg) ? stats.avg : 0;
    const targetCritical = Number.isFinite(stats.critical) ? stats.critical : 0;

    let frameId = 0;
    const durationMs = 750;
    const start = performance.now();

    const animate = (now) => {
      const progress = Math.min((now - start) / durationMs, 1);
      setAnimatedStats({
        monitored: targetMonitored * progress,
        avg: targetAvg * progress,
        critical: targetCritical * progress,
      });

      if (progress < 1) {
        frameId = requestAnimationFrame(animate);
      }
    };

    frameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameId);
  }, [stats.monitored, stats.avg, stats.critical]);

  const onSelectProject = (project) => {
    navigate(`/project/${project.owner}/${project.repo}`);
  };

  return (
    <main className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8">
      <section className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div
          data-testid="stat-card-monitored"
          className="rounded-xl border border-border border-t-risk-green bg-surface p-4 transition-transform hover:-translate-y-1"
        >
          <p className="text-xs text-slate-400">Monitored Repos</p>
          <p className="mt-2 text-2xl font-semibold">{Math.round(animatedStats.monitored)}</p>
        </div>
        <div
          data-testid="stat-card-avg"
          className="rounded-xl border border-border border-t-slate-500 bg-surface p-4 transition-transform hover:-translate-y-1"
        >
          <p className="text-xs text-slate-400">Avg Risk Score</p>
          <p className="mt-2 text-2xl font-semibold">
            {Number.isFinite(animatedStats.avg) ? animatedStats.avg.toFixed(1) : "0.0"}
          </p>
        </div>
        <div
          data-testid="stat-card-critical"
          className="rounded-xl border border-border border-t-risk-red bg-surface p-4 transition-transform hover:-translate-y-1"
        >
          <p className="text-xs text-slate-400">Critical Flags</p>
          <p className="mt-2 text-2xl font-semibold text-risk-red">{Math.round(animatedStats.critical)}</p>
        </div>
        <div
          data-testid="stat-card-updated"
          className="rounded-xl border border-border border-t-slate-500 bg-surface p-4 transition-transform hover:-translate-y-1"
        >
          <p className="text-xs text-slate-400">Last Updated</p>
          <p className="mt-2 text-sm font-semibold">{stats.updated}</p>
        </div>
      </section>

      {error ? (
        <div className="mb-4 rounded-xl border border-risk-red/50 bg-risk-red/10 p-4 text-sm text-red-200">{error}</div>
      ) : null}

      {loading ? (
        <RiskTable projects={null} riskScores={{}} onSelectProject={onSelectProject} isLoading={true} />
      ) : (
        <RiskTable
          projects={projects}
          riskScores={riskScores}
          onSelectProject={onSelectProject}
          isLoading={isRiskLoading}
        />
      )}
    </main>
  );
}
