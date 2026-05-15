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

test("renders the role-aware dashboard shell", async () => {
  render(<App />);

  expect(await screen.findByRole("heading", { name: "Network Situation" })).toBeInTheDocument();
  expect(screen.queryByText("Users & RBAC")).not.toBeInTheDocument();
});
