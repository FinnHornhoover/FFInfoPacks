import { describe, expect, it } from "vitest";
import { bannedKeys, parseExclusions, serializeExclusions } from "./exclusions";

const SOURCE = `areas:
  - [0, 0, 0, 0]
npc:
  - 700
weaponitem:
  - 9
  - 2
hatitem:
  - 4
generalitem:
  - -1
`;

describe("exclusion YAML", () => {
  it("derives banned status from category and ID", () => {
    const banned = bannedKeys(parseExclusions(SOURCE));
    expect([...banned]).toContain("weaponitem:9");
    expect([...banned]).toContain("generalitem:-1");
    expect([...banned]).not.toContain("npc:700");
  });

  it("updates only item lists and sorts IDs", () => {
    const data = parseExclusions(SOURCE);
    const banned = bannedKeys(data);
    banned.delete("weaponitem:9");
    banned.add("weaponitem:3");
    const output = parseExclusions(serializeExclusions(data, banned));
    expect(output.areas).toEqual([[0, 0, 0, 0]]);
    expect(output.npc).toEqual([700]);
    expect(output.weaponitem).toEqual([2, 3]);
    expect(output.generalitem).toEqual([-1]);
  });
});
