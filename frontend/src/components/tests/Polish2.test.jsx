import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import NewsFeed from "../NewsFeed";
import ContributorChart from "../ContributorChart";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }) => <div data-testid="responsive">{children}</div>,
  AreaChart: ({ data, children }) => (
    <div data-testid="area-chart" data-length={Array.isArray(data) ? data.length : 0}>
      {children}
    </div>
  ),
  CartesianGrid: () => <div data-testid="grid" />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  Tooltip: () => <div data-testid="tooltip" />,
  Area: () => <div data-testid="area" />,
}));

describe("V2-06 dashboard polish", () => {
  afterEach(() => {
    cleanup();
  });

  it("NewsFeed renders empty state when all articles are placeholders", () => {
    render(
      <NewsFeed
        items={[
          {
            title: "Weekly update 1 for project ansible/ansible",
            url: "https://example.com/1",
            sentiment_score: 0.1,
            published_at: "2026-03-20T00:00:00Z",
          },
          {
            title: "Weekly update 2 for project kubernetes/kubernetes",
            url: "https://example.com/2",
            sentiment_score: -0.1,
            published_at: "2026-03-21T00:00:00Z",
          },
        ]}
      />
    );

    expect(screen.getByText("No recent news articles found for this project")).toBeInTheDocument();
    expect(screen.queryByText("Weekly update 1 for project ansible/ansible")).not.toBeInTheDocument();
  });

  it("NewsFeed renders real articles when they exist alongside placeholders", () => {
    render(
      <NewsFeed
        items={[
          {
            title: "Weekly update 3 for project grafana/grafana",
            url: "https://example.com/mock",
            sentiment_score: 0,
            published_at: "2026-03-20T00:00:00Z",
          },
          {
            title: "Grafana ships reliability improvements",
            url: "https://example.com/real",
            sentiment_score: 0.6,
            published_at: "2026-03-22T00:00:00Z",
          },
        ]}
      />
    );

    expect(screen.getByText("Grafana ships reliability improvements")).toBeInTheDocument();
    expect(screen.queryByText("Weekly update 3 for project grafana/grafana")).not.toBeInTheDocument();
  });

  it("ContributorChart renders with sliced data when more than 16 points provided", () => {
    const snapshots = Array.from({ length: 20 }, (_, index) => ({
      week: `2026-01-${String(index + 1).padStart(2, "0")}T00:00:00Z`,
      contributor_count: index + 1,
    }));

    render(<ContributorChart snapshots={snapshots} />);

    expect(screen.getByTestId("area-chart")).toHaveAttribute("data-length", "16");
  });
});
