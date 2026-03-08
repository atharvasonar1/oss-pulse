const API_BASE = "/api";

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

export async function fetchProjects() {
  return safeFetch("/projects");
}

export async function fetchRiskScore(projectId) {
  return safeFetch(`/projects/${projectId}/risk-score`);
}
