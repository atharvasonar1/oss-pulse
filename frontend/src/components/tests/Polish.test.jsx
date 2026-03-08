import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../../App";
import RiskTable from "../RiskTable";
import ScoreBadge from "../ScoreBadge";
import Overview from "../../pages/Overview";
import ProjectDetail from "../../pages/ProjectDetail";

const navigateMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => navigateMock,
    useParams: () => ({ owner: "ansible", repo: "ansible" }),
  };
});

vi.mock("../../lib/api", () => ({
  fetchProjects: vi.fn(),
  fetchRiskScore: vi.fn(),
  fetchProjectByOwnerRepo: vi.fn(),
  fetchSnapshots: vi.fn(),
}));

import {
  fetchProjectByOwnerRepo,
  fetchProjects,
  fetchRiskScore,
  fetchSnapshots,
} from "../../lib/api";

describe("Dashboard polish", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();

    fetchProjects.mockResolvedValue({
      ok: true,
      data: [{ id: 1, owner: "ansible", repo: "ansible" }],
    });
    fetchRiskScore.mockResolvedValue({
      ok: true,
      data: {
        score: 73,
        project_id: 1,
        scored_at: "2026-03-09T00:00:00Z",
        top_features: [{ feature: "bus_factor", shap_value: 0.4, direction: "risk" }],
      },
    });
    fetchProjectByOwnerRepo.mockResolvedValue({
      ok: true,
      data: { id: 1, owner: "ansible", repo: "ansible" },
    });
    fetchSnapshots.mockResolvedValue({
      ok: true,
      data: [
        {
          week: "2026-03-02T00:00:00Z",
          contributor_count: 8,
          open_issues: 12,
          closed_issues: 10,
          news_items: [],
        },
      ],
    });
  });

  it("ScoreBadge ring variant renders SVG element", () => {
    render(<ScoreBadge score={73} variant="ring" />);
    expect(screen.getByTestId("score-ring-svg")).toBeInTheDocument();
  });

  it("RiskTable calls onSelectProject when Enter is pressed on row", () => {
    const onSelectProject = vi.fn();
    render(
      <RiskTable
        projects={[{ id: 1, owner: "ansible", repo: "ansible" }]}
        riskScores={{ 1: { score: 73, top_features: [], scored_at: "2026-03-09T00:00:00Z" } }}
        onSelectProject={onSelectProject}
        isLoading={false}
      />
    );

    const row = screen.getByRole("button");
    fireEvent.keyDown(row, { key: "Enter" });

    expect(onSelectProject).toHaveBeenCalledTimes(1);
    expect(onSelectProject).toHaveBeenCalledWith({ id: 1, owner: "ansible", repo: "ansible" });
  });

  it("ProjectDetail health summary shows elevated risk for score 73", async () => {
    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByText(/elevated risk/i)).toBeInTheDocument();
    });
  });

  it("Overview stat cards render with colored top borders", async () => {
    render(<Overview />);

    await waitFor(() => {
      expect(screen.getByTestId("stat-card-monitored")).toBeInTheDocument();
      expect(screen.getByTestId("stat-card-avg")).toBeInTheDocument();
      expect(screen.getByTestId("stat-card-critical")).toBeInTheDocument();
      expect(screen.getByTestId("stat-card-updated")).toBeInTheDocument();
    });

    expect(screen.getByTestId("stat-card-monitored").className).toContain("border-t-risk-green");
    expect(screen.getByTestId("stat-card-avg").className).toContain("border-t-slate-500");
    expect(screen.getByTestId("stat-card-critical").className).toContain("border-t-risk-red");
    expect(screen.getByTestId("stat-card-updated").className).toContain("border-t-slate-500");
  });

  it("App header renders live indicator with animate-pulse class", () => {
    render(<App />);

    const dot = screen.getByTestId("live-indicator-dot");
    expect(dot).toBeInTheDocument();
    expect(dot.className).toContain("animate-pulse");
  });
});
