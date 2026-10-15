/** Tests for display logic that the teacher relies on being correct. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "@/components/ui/primitives";
import { formatDate, maskKey, pct } from "@/lib/utils";

describe("pct", () => {
  it("formats a percentage to the requested precision", () => {
    expect(pct(77.456, 2)).toBe("77.46%");
    expect(pct(75, 1)).toBe("75.0%");
    expect(pct(100, 0)).toBe("100%");
  });

  it("renders an em dash for a missing value rather than 0%", () => {
    // Showing 0% for absent data would misrepresent it as a real measurement.
    expect(pct(null)).toBe("—");
    expect(pct(undefined)).toBe("—");
  });

  it("shows a genuine zero as 0%", () => {
    expect(pct(0, 1)).toBe("0.0%");
  });
});

describe("maskKey", () => {
  it("keeps only enough characters to identify the key", () => {
    const masked = maskKey("sk-proj-ABCDEFGHIJKLMNOP");
    expect(masked).not.toContain("ABCDEFGHIJKLMNOP");
    expect(masked.startsWith("sk-p")).toBe(true);
    expect(masked.endsWith("MNOP")).toBe(true);
  });

  it("fully masks a short key", () => {
    expect(maskKey("abc123")).toBe("••••••");
  });

  it("handles an empty key", () => {
    expect(maskKey("")).toBe("");
  });
});

describe("formatDate", () => {
  it("renders an em dash for a missing date", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate(undefined)).toBe("—");
  });

  it("returns the original string when it is not a date", () => {
    expect(formatDate("not-a-date")).toBe("not-a-date");
  });

  it("formats a valid ISO date", () => {
    expect(formatDate("2026-04-15")).toMatch(/2026/);
  });
});

describe("StatusBadge", () => {
  it("conveys status as text, not colour alone", () => {
    // Accessibility: the label must be readable without colour perception.
    render(<StatusBadge status="Below threshold" />);
    expect(screen.getByText("Below threshold")).toBeInTheDocument();
  });

  it("renders each status distinctly", () => {
    const { rerender } = render(<StatusBadge status="At risk" />);
    expect(screen.getByText("At risk")).toBeInTheDocument();

    rerender(<StatusBadge status="Meeting threshold" />);
    expect(screen.getByText("Meeting threshold")).toBeInTheDocument();
  });
});
