import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import App from "./App";
import { visibleNavItems } from "./lib/navigation";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((input: string) => {
      if (input.endsWith("/me/")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: 1,
            username: "admin@coalflow.local",
            email: "admin@coalflow.local",
            is_active: true,
            memberships: [],
            assignments: [],
            permissions: ["dashboard.view"],
          }),
        });
      }

      return Promise.resolve({
        ok: true,
        json: async () => [],
      });
    }),
  );
});

test("filters navigation by permission", () => {
  expect(visibleNavItems(["dashboard.view"]).map((item) => item.label)).toEqual([
    "Network Situation",
  ]);
});

test("shows implemented admin submodules without exposing future locked routes", () => {
  expect(
    visibleNavItems(["dashboard.view", "masterdata.view", "schedule.view"]).map(
      (item) => item.label,
    ),
  ).toEqual([
    "Network Situation",
    "OGV Demand & Laycan",
    "Coal Grade Sequence",
    "Tide & Bridge Window",
    "Tug/Barge Assignment",
    "Jetty Loading",
    "CTS / Floating Crane",
    "Published Plan & Schedule",
    "Exception Center",
    "Master Data Console",
  ]);
});

test("exposes chunk 5 recovery routes by workflow permission", () => {
  expect(
    visibleNavItems([
      "dashboard.view",
      "schedule.view",
      "schedule.edit",
      "schedule.approve",
    ]).map((item) => item.label),
  ).toContain("Simulation Workspace");
  expect(
    visibleNavItems([
      "dashboard.view",
      "schedule.view",
      "schedule.edit",
      "schedule.approve",
    ]).map((item) => item.label),
  ).toContain("Approvals & Publishing");
});

test("renders the role-aware dashboard shell", async () => {
  render(<App />);

  expect(await screen.findByRole("heading", { name: "Network Situation" })).toBeInTheDocument();
  expect(screen.queryByText("Users & RBAC")).not.toBeInTheDocument();
});
