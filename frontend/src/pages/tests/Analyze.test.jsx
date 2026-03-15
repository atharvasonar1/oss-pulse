import "@testing-library/jest-dom/vitest";

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Analyze from "../Analyze";

vi.mock("../../lib/api", () => ({
  analyzeManifest: vi.fn(),
}));

describe("Analyze page", () => {
  it("renders upload dropzone on mount", () => {
    render(<Analyze />);

    expect(screen.getByText("Upload dependency manifest")).toBeInTheDocument();
    expect(screen.getByLabelText("Upload dependency manifest")).toBeInTheDocument();
  });
});
