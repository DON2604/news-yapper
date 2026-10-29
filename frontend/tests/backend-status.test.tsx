import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BackendStatus } from "@/components/layout/BackendStatus";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("BackendStatus", () => {
  it("shows the backend as up when /api/health reports ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ backend: "up", database: "ok", version: "0.1.0" }),
      }),
    );
    const view = render(<BackendStatus />);
    expect(await screen.findByText("Backend up")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("title", "Backend up. Database ok");
    view.unmount();
  });

  it("shows the backend as down when the health check cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
    const view = render(<BackendStatus />);
    expect(await screen.findByText("Backend down")).toBeInTheDocument();
    view.unmount();
  });
});
