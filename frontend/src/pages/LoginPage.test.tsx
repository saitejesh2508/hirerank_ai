import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LoginPage from "./LoginPage";

describe("LoginPage", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("authenticates and returns the selected demo role", async () => {
    const user = { id: 1, email: "recruiter@hirerank.demo", full_name: "Aarav Mehta", role: "recruiter", organization_id: null };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ access_token: "signed-token", token_type: "bearer", user }),
    }));
    const onLogin = vi.fn();
    render(<LoginPage onLogin={onLogin} />);
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: user.email } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "Recruiter@123" } });
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => expect(onLogin).toHaveBeenCalledWith(user));
    expect(localStorage.getItem("hirerank_token")).toBe("signed-token");
  });

  it("shows a clear login failure without crashing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Email or password is incorrect" }),
    }));
    render(<LoginPage onLogin={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "wrong@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));
    expect(await screen.findByText("Email or password is incorrect")).toBeInTheDocument();
  });
});
