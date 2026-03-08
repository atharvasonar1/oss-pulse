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
  const [error, setError] = useState("");

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

      if (loadedProjects.length === 0) {
        setRiskScores({});
        setLoading(false);
        return;
      }

      const scoreEntries = await Promise.all(
        loadedProjects.map(async (project) => {
          const scoreResp = await fetchRiskScore(project.id);
          return [project.id, scoreResp.ok ? scoreResp.data : null];
        })
      );

      if (!active) return;
      setRiskScores(Object.fromEntries(scoreEntries));
      setLoading(false);
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
    const avg = scores.length ? (scores.reduce((sum, value) => sum + value, 0) / scores.length).toFixed(1) : "0.0";
    const critical = scores.filter((score) => score >= 60).length;

    return {
      monitored,
      avg,
      critical,
      updated: getLastUpdated(riskScores),
    };
  }, [projects, riskScores]);

  const onSelectProject = (project) => {
    navigate(`/project/${project.owner}/${project.repo}`);
  };

  return (
    <main className="mx-auto w-full max-w-7xl p-4 sm:p-6 lg:p-8">
      <section className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl border border-border bg-surface p-4">
          <p className="text-xs text-slate-400">Monitored Repos</p>
          <p className="mt-2 text-2xl font-semibold">{stats.monitored}</p>
        </div>
        <div className="rounded-xl border border-border bg-surface p-4">
          <p className="text-xs text-slate-400">Avg Risk Score</p>
          <p className="mt-2 text-2xl font-semibold">{stats.avg}</p>
        </div>
        <div className="rounded-xl border border-border bg-surface p-4">
          <p className="text-xs text-slate-400">Critical Flags</p>
          <p className="mt-2 text-2xl font-semibold text-risk-red">{stats.critical}</p>
        </div>
        <div className="rounded-xl border border-border bg-surface p-4">
          <p className="text-xs text-slate-400">Last Updated</p>
          <p className="mt-2 text-sm font-semibold">{stats.updated}</p>
        </div>
      </section>

      {error ? (
        <div className="mb-4 rounded-xl border border-risk-red/50 bg-risk-red/10 p-4 text-sm text-red-200">{error}</div>
      ) : null}

      {loading ? (
        <RiskTable projects={null} riskScores={{}} onSelectProject={onSelectProject} />
      ) : (
        <RiskTable projects={projects} riskScores={riskScores} onSelectProject={onSelectProject} />
      )}
    </main>
  );
}
