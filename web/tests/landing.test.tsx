import { render, screen } from "@testing-library/react";
import LandingPage from "@/app/(public)/page";

describe("LandingPage", () => {
  it("renders the headline", () => {
    render(<LandingPage />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/check in with yourself/i);
  });

  it("always states that Calma is a screening tool, not a diagnosis", () => {
    render(<LandingPage />);
    expect(screen.getByText(/screening tool, not a diagnosis/i)).toBeInTheDocument();
  });

  it("shows the India crisis helplines", () => {
    render(<LandingPage />);
    expect(screen.getByText(/14416/)).toBeInTheDocument();
    expect(screen.getByText(/112/)).toBeInTheDocument();
  });
});
