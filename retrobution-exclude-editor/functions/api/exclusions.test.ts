import { describe, expect, it } from "vitest";
import { validateChange } from "./exclusions";

const CURRENT = `areas:
  - [0, 0, 0, 0]
npc:
  - 700
weaponitem:
  - 2
hatitem:
  - 4
backitem: []
glassitem: []
pantsitem: []
shirtsitem: []
shoesitem: []
vehicleitem:
  - -1
generalitem:
  - -1
chestitem:
  - -1
`;

describe("Pages Function exclusion validation", () => {
  it("allows sorted item-only changes", () => {
    const proposed = CURRENT.replace("  - 2\nhatitem:", "  - 2\n  - 9\nhatitem:");
    expect(() => validateChange(CURRENT, proposed)).not.toThrow();
  });

  it("rejects changes to non-item exclusions", () => {
    const proposed = CURRENT.replace("  - 700", "  - 701");
    expect(() => validateChange(CURRENT, proposed)).toThrow("Only item exclusion lists");
  });

  it("rejects unsorted or duplicate item IDs", () => {
    const unsorted = CURRENT.replace("  - 2\nhatitem:", "  - 9\n  - 2\nhatitem:");
    const duplicate = CURRENT.replace("  - 2\nhatitem:", "  - 2\n  - 2\nhatitem:");
    expect(() => validateChange(CURRENT, unsorted)).toThrow("must be sorted");
    expect(() => validateChange(CURRENT, duplicate)).toThrow("duplicate");
  });
});
