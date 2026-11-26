import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";
import { QuestionCard } from "@/components/calma/question-card";
import { CrisisScreen } from "@/components/calma/crisis-screen";
import { SeverityGauge } from "@/components/calma/severity-gauge";
import { ShapChart } from "@/components/calma/shap-chart";
import { ProgressBar } from "@/components/calma/progress-bar";
import { toneFor } from "@/lib/bands";
import { renderIntl } from "./intl";

// Placeholder wording only: real item texts always come from the API.
const OPTIONS = [0, 1, 2, 3].map((v) => ({ value: v, label: `Option ${v}` }));

describe("QuestionCard", () => {
  it("renders a radiogroup with large options and answers by click", () => {
    const onAnswer = vi.fn();
    renderIntl(<QuestionCard text="Placeholder item" options={OPTIONS} value={undefined} onAnswer={onAnswer} progressLabel="Question 1 of 7" />);
    expect(screen.getByRole("radiogroup")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: /Option 2/ }));
    expect(onAnswer).toHaveBeenCalledWith(2);
  });

  it("answers with keyboard shortcuts 1-4", () => {
    const onAnswer = vi.fn();
    renderIntl(<QuestionCard text="Placeholder item" options={OPTIONS} value={undefined} onAnswer={onAnswer} progressLabel="" />);
    fireEvent.keyDown(window, { key: "4" });
    expect(onAnswer).toHaveBeenCalledWith(3);
    fireEvent.keyDown(window, { key: "9" });
    expect(onAnswer).toHaveBeenCalledTimes(1);
  });

  it("marks the selected option", () => {
    renderIntl(<QuestionCard text="Placeholder item" options={OPTIONS} value={1} onAnswer={() => {}} progressLabel="" />);
    expect(screen.getByRole("radio", { name: /Option 1/ })).toHaveAttribute("aria-checked", "true");
  });
});

describe("CrisisScreen", () => {
  it("shows helplines and lets the user continue to results", () => {
    const onContinue = vi.fn();
    renderIntl(
      <CrisisScreen
        helplines={{ country: "India", helplines: [{ name: "Tele-MANAS", number: "14416", alt_number: "1-800-891-4416" }, { name: "Emergency", number: "112" }] }}
        onContinue={onContinue}
      />,
    );
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /don't have to go through this alone/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /14416/ })).toHaveAttribute("href", "tel:14416");
    expect(screen.getByRole("link", { name: /112/ })).toHaveAttribute("href", "tel:112");
    fireEvent.click(screen.getByRole("button", { name: /continue to my results/i }));
    expect(onContinue).toHaveBeenCalled();
  });
});

describe("SeverityGauge", () => {
  it("has an accessible label", () => {
    renderIntl(<SeverityGauge score={10} max={21} bands={[{ min: 0, max: 4, label: "A", level: 0 }, { min: 5, max: 21, label: "B", level: 1 }]} label="GAD-7 score 10 of 21" />);
    expect(screen.getByRole("img", { name: "GAD-7 score 10 of 21" })).toBeInTheDocument();
  });
});

describe("ShapChart", () => {
  it("lists factors with direction", () => {
    renderIntl(<ShapChart factors={[{ feature: "gad7_2", label: "GAD-7 item 2", impact: 0.5 }, { feature: "sleep_hours", label: "Sleep hours", impact: -0.2 }]} />);
    expect(screen.getByText("GAD-7 item 2")).toBeInTheDocument();
    expect(screen.getByText("raised the estimate")).toBeInTheDocument();
    expect(screen.getByText("lowered the estimate")).toBeInTheDocument();
  });
});

describe("ProgressBar", () => {
  it("exposes progress values", () => {
    renderIntl(<ProgressBar value={3} max={7} label="Overall progress" />);
    const bar = screen.getByRole("progressbar", { name: "Overall progress" });
    expect(bar).toHaveAttribute("aria-valuenow", "3");
  });
});

describe("toneFor", () => {
  it("never uses the severe colour for two-level screens", () => {
    expect(toneFor(1, 2)).toBe("moderate");
    expect(toneFor(0, 2)).toBe("minimal");
    expect(toneFor(3, 4)).toBe("severe");
    expect(toneFor(4, 5)).toBe("severe");
  });
});
