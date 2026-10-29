import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CandyButton } from "@/components/design-system/CandyButton";
import { StickyNote } from "@/components/design-system/StickyNote";
import { QuizOption } from "@/components/quiz/QuizOption";

describe("QuizOption", () => {
  it("announces correctness with text, not colour alone", () => {
    const { rerender } = render(<QuizOption letter="A" text="Pragyan" state="correct" disabled onSelect={() => {}} />);
    expect(screen.getByText("Correct answer")).toBeInTheDocument();
    rerender(<QuizOption letter="B" text="Vikram" state="wrong" disabled onSelect={() => {}} />);
    expect(screen.getByText("Your answer")).toBeInTheDocument();
    rerender(<QuizOption letter="C" text="Aditya" state="idle" disabled={false} onSelect={() => {}} />);
    expect(screen.queryByText(/answer$/)).not.toBeInTheDocument();
  });

  it("calls onSelect when enabled", () => {
    const onSelect = vi.fn();
    render(<QuizOption letter="A" text="Option" state="idle" disabled={false} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onSelect).toHaveBeenCalledOnce();
  });
});

describe("StickyNote", () => {
  it("renders user text as text nodes, never as HTML", () => {
    const { container } = render(
      <StickyNote id="n1" title="<img src=x onerror=alert(1)>" body={"- first point\n<script>alert('x')</script>"} color="mango" tags={["polity"]} />,
    );
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
    expect(screen.getByText("first point")).toBeInTheDocument();
    expect(screen.getByText("#polity")).toBeInTheDocument();
  });
});

describe("CandyButton", () => {
  it("defaults to type=button and keeps a 44px touch target class", () => {
    render(<CandyButton>Stick it!</CandyButton>);
    const button = screen.getByRole("button", { name: "Stick it!" });
    expect(button).toHaveAttribute("type", "button");
    expect(button.className).toContain("min-h-12");
  });
});
