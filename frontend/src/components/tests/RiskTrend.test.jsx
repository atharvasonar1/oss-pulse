import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ProjectDetail from "../../pages/ProjectDetail";
import RiskTrendChart from "../RiskTrendChart";


const navigateMock = vi.fn();

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
  useParams: () => ({ owner: "ansible", repo: "ansible" }),
}));

vi.mock("../../lib/api", () => ({
  fetchProjectByOwnerRepo: vi.fn(),
  fetchRiskScore: vi.fn(),
  fetchRiskHistory: vi.fn(),
  fetchSnapshots: vi.fn(),
}));

import { fetchProjectByOwnerRepo, fetchRiskHistory, fetchRiskScore, fetchSnapshots } from "../../lib/api";


describe("Risk trend", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("RiskTrendChart renders loading skeleton when history is null", () => {
    const { container } = render(<RiskTrendChart history={null} />);
    expect(screen.getByText("Risk Score Over Time")).toBeInTheDocument();
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("RiskTrendChart renders empty state when history is empty", () => {
    render(<RiskTrendChart history={[]} />);
    expect(screen.getByText("No risk history available.")).toBeInTheDocument();
  });

  it("RiskTrendChart renders chart when history has data points", () => {
    const history = [
      { score: 41, scored_at: "2026-03-01T00:00:00Z" },
      { score: 57, scored_at: "2026-03-08T00:00:00Z" },
      { score: 66, scored_at: "2026-03-15T00:00:00Z" },
    ];
    const { container } = render(<RiskTrendChart history={history} />);
    expect(screen.getByText("Risk Score Over Time")).toBeInTheDocument();
    expect(container.querySelector(".recharts-responsive-container")).toBeInTheDocument();
  });

  it("ProjectDetail fetches risk history on mount", async () => {
    fetchProjectByOwnerRepo.mockResolvedValue({
      ok: true,
      data: { id: 1, owner: "ansible", repo: "ansible" },
    });
    fetchRiskScore.mockResolvedValue({
      ok: true,
      data: {
        score: 64,
        scored_at: "2026-03-15T00:00:00Z",
        project_id: 1,
        top_features: [{ feature: "bus_factor", shap_value: 0.3, direction: "risk" }],
      },
    });
    fetchRiskHistory.mockResolvedValue({
      ok: true,
      data: [
        { score: 44, scored_at: "2026-03-01T00:00:00Z" },
        { score: 64, scored_at: "2026-03-15T00:00:00Z" },
      ],
    });
    fetchSnapshots.mockResolvedValue({
      ok: true,
      data: [
        {
          week: "2026-03-15T00:00:00Z",
          contributor_count: 10,
          open_issues: 8,
          closed_issues: 13,
          news_items: [],
        },
      ],
    });

    render(<ProjectDetail />);

    await waitFor(() => {
      expect(fetchRiskHistory).toHaveBeenCalledTimes(1);
      expect(fetchRiskHistory).toHaveBeenCalledWith(1);
    });
  });
});
