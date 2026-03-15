const API_BASE = import.meta.env.VITE_API_URL || "/api";

async function safeFetch(path) {
  try {
    const response = await fetch(`${API_BASE}${path}`);
    const json = await response.json().catch(() => null);

    if (!response.ok) {
      if (json && typeof json === "object") {
        return {
          ok: false,
          error: json.error || `Request failed (${response.status})`,
          status: json.status || response.status,
        };
      }
      return { ok: false, error: `Request failed (${response.status})`, status: response.status };
    }

    if (json && typeof json === "object") {
      return json;
    }

    return { ok: false, error: "Invalid API response", status: 500 };
  } catch (_error) {
    return { ok: false, error: "Network error", status: 503 };
  }
}

function buildMockSnapshots(projectId) {
  const baseDate = new Date("2026-03-02T00:00:00Z");
  const seed = Number(projectId) || 1;
  return [...Array(12)].map((_, index) => {
    const date = new Date(baseDate);
    date.setUTCDate(baseDate.getUTCDate() - (11 - index) * 7);

    const contributor_count = Math.max(1, 9 + ((seed + index) % 5) - Math.floor(index / 5));
    const commit_count = 20 + ((seed * 3 + index * 2) % 18);
    const open_issues = 8 + ((seed + index * 4) % 14);
    const closed_issues = 10 + ((seed * 2 + index * 5) % 16);

    return {
      week: date.toISOString(),
      contributor_count,
      commit_count,
      open_issues,
      closed_issues,
      news_items: index % 3 === 0
        ? [
            {
              title: `Weekly update ${index + 1} for project ${projectId}`,
              url: `https://example.com/news/${projectId}/${index + 1}`,
              sentiment_score: index % 2 === 0 ? 0.25 : -0.2,
              published_at: date.toISOString(),
            },
          ]
        : [],
    };
  });
}

export async function fetchProjects() {
  return safeFetch("/projects");
}

export async function fetchRiskScore(projectId) {
  return safeFetch(`/projects/${projectId}/risk-score`);
}

export async function fetchRiskHistory(projectId) {
  return safeFetch(`/projects/${projectId}/risk-history`);
}

export async function fetchProjectByOwnerRepo(owner, repo) {
  const projectsResp = await fetchProjects();
  if (!projectsResp.ok) {
    return projectsResp;
  }

  const targetOwner = String(owner || "").trim().toLowerCase();
  const targetRepo = String(repo || "").trim().toLowerCase();
  const projects = Array.isArray(projectsResp.data) ? projectsResp.data : [];

  const project = projects.find(
    (item) => String(item?.owner || "").toLowerCase() === targetOwner && String(item?.repo || "").toLowerCase() === targetRepo
  );

  return { ok: true, data: project || null };
}

export async function fetchSnapshots(projectId) {
  const response = await safeFetch(`/projects/${projectId}/snapshots`);
  if (response.ok && Array.isArray(response.data)) {
    return response;
  }

  return { ok: true, data: buildMockSnapshots(projectId) };
}

export async function analyzeManifest(file) {
  try {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      body: formData,
    });
    const json = await response.json().catch(() => null);

    if (!response.ok) {
      if (json && typeof json === "object") {
        return {
          ok: false,
          error: json.error || `Request failed (${response.status})`,
          status: json.status || response.status,
        };
      }
      return { ok: false, error: `Request failed (${response.status})`, status: response.status };
    }

    if (json && typeof json === "object") {
      return json;
    }
    return { ok: false, error: "Invalid API response", status: 500 };
  } catch (_error) {
    return { ok: false, error: "Network error", status: 503 };
  }
}
