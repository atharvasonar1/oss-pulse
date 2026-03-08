import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import NewsFeed from "../NewsFeed";
import ProjectDetail from "../../pages/ProjectDetail";
import ShapExplainer from "../ShapExplainer";

const navigateMock = vi.fn();
const paramsMock = { owner: "ansible", repo: "ansible" };

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
  useParams: () => paramsMock,
}));

vi.mock("../../lib/api", () => ({
  fetchProjectByOwnerRepo: vi.fn(),
  fetchRiskScore: vi.fn(),
  fetchSnapshots: vi.fn(),
}));

import { fetchProjectByOwnerRepo, fetchRiskScore, fetchSnapshots } from "../../lib/api";

describe("ProjectDetail", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    fetchProjectByOwnerRepo.mockResolvedValue({
      ok: true,
      data: { id: 1, owner: "ansible", repo: "ansible" },
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
    fetchSnapshots.mockResolvedValue({
      ok: true,
      data: [
        {
          week: "2026-02-02T00:00:00Z",
          contributor_count: 9,
          open_issues: 10,
          closed_issues: 14,
          news_items: [],
        },
      ],
    });
  });

  it("renders project title after data loads", async () => {
    render(<ProjectDetail />);

    await waitFor(() => {
      expect(screen.getByText("ansible/ansible")).toBeInTheDocument();
    });
  });

  it("renders Why this score heading", () => {
    render(<ShapExplainer topFeatures={[{ feature: "bus_factor", shap_value: 0.4, direction: "risk" }]} />);
    expect(screen.getByText("Why this score?")).toBeInTheDocument();
  });

  it("renders ShapExplainer empty state when topFeatures is empty", () => {
    render(<ShapExplainer topFeatures={[]} />);
    expect(screen.getByText("No feature explanations available yet.")).toBeInTheDocument();
  });

  it("renders No recent news when NewsFeed items empty", () => {
    render(<NewsFeed items={[]} />);
    expect(screen.getByText("No recent news")).toBeInTheDocument();
  });

  it("renders article titles when NewsFeed items provided", () => {
    render(
      <NewsFeed
        items={[
          {
            title: "Maintainer update improves project stability",
            url: "https://example.com/1",
            sentiment_score: 0.5,
            published_at: "2026-03-08T00:00:00Z",
          },
          {
            title: "Critical dependency fix released",
            url: "https://example.com/2",
            sentiment_score: 0.2,
            published_at: "2026-03-07T00:00:00Z",
          },
        ]}
      />
    );

    expect(screen.getByText("Maintainer update improves project stability")).toBeInTheDocument();
    expect(screen.getByText("Critical dependency fix released")).toBeInTheDocument();
  });
});
