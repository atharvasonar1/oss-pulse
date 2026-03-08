import "@testing-library/jest-dom/vitest";

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Overview from "../../pages/Overview";
import ScoreBadge from "../ScoreBadge";

vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock("../../lib/api", () => ({
  fetchProjects: vi.fn(),
  fetchRiskScore: vi.fn(),
}));

import { fetchProjects, fetchRiskScore } from "../../lib/api";

describe("Overview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state initially", () => {
    fetchProjects.mockImplementation(() => new Promise(() => {}));

    render(<Overview />);

    expect(screen.getByText("Monitored Repos")).toBeInTheDocument();
    expect(document.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders project rows after data loads", async () => {
    fetchProjects.mockResolvedValue({
      ok: true,
      data: [
        { id: 1, owner: "ansible", repo: "ansible" },
        { id: 2, owner: "cli", repo: "cli" },
      ],
    });
    fetchRiskScore.mockResolvedValue({
      ok: true,
      data: {
        score: 75,
        top_features: [{ feature: "bus_factor", shap_value: 0.4, direction: "risk" }],
        scored_at: "2026-03-08T00:00:00Z",
        project_id: 1,
      },
    });

    render(<Overview />);

    await waitFor(() => {
      expect(screen.getByText("ansible/ansible")).toBeInTheDocument();
      expect(screen.getByText("cli/cli")).toBeInTheDocument();
    });
  });

  it("renders empty state when no projects returned", async () => {
    fetchProjects.mockResolvedValue({ ok: true, data: [] });

    render(<Overview />);

    await waitFor(() => {
      expect(screen.getByText("No projects found.")).toBeInTheDocument();
    });
  });
});

describe("ScoreBadge", () => {
  it("renders red for score 75", () => {
    const { container } = render(<ScoreBadge score={75} />);
    expect(container.querySelector(".text-risk-red")).toBeInTheDocument();
  });

  it("renders green for score 15", () => {
    const { container } = render(<ScoreBadge score={15} />);
    expect(container.querySelector(".text-risk-green")).toBeInTheDocument();
  });
});
