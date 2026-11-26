import { screen } from "@testing-library/react";
import LandingPage from "@/app/(public)/page";
import { renderIntl } from "./intl";
import hi from "@/messages/hi.json";

describe("LandingPage", () => {
  it("renders the headline and a start link to consent", () => {
    renderIntl(<LandingPage />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/check in with yourself/i);
    expect(screen.getByRole("link", { name: /start a check-in/i })).toHaveAttribute("href", "/consent");
  });

  it("always states that Calma is a screening tool, not a diagnosis", () => {
    renderIntl(<LandingPage />);
    expect(screen.getByText(/screening tool, not a diagnosis/i)).toBeInTheDocument();
  });

  it("shows the India crisis helplines", () => {
    renderIntl(<LandingPage />);
    expect(screen.getByText(/14416/)).toBeInTheDocument();
    expect(screen.getByText(/112/)).toBeInTheDocument();
  });

  it("renders in Hindi", () => {
    renderIntl(<LandingPage />, "hi", hi);
    expect(screen.getByRole("link", { name: "चेक-इन शुरू करें" })).toBeInTheDocument();
  });
});
