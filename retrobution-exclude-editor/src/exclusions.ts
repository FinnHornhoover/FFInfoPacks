import { parse, stringify } from "yaml";
import { ITEM_CATEGORIES, type CatalogItem, type ExclusionData, type ItemCategory } from "./types";

export function itemKey(item: Pick<CatalogItem, "category" | "id">): string {
  return `${item.category}:${item.id}`;
}

function integerIds(value: unknown): number[] {
  if (!Array.isArray(value) || value.some((entry) => !Number.isInteger(entry))) {
    return [];
  }
  return value as number[];
}

export function parseExclusions(source: string): ExclusionData {
  const parsed = parse(source);
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("The exclusion file must contain a YAML mapping.");
  }
  return parsed as ExclusionData;
}

export function bannedKeys(data: ExclusionData): Set<string> {
  const result = new Set<string>();
  for (const category of ITEM_CATEGORIES) {
    for (const id of integerIds(data[category])) {
      result.add(`${category}:${id}`);
    }
  }
  return result;
}

export function serializeExclusions(data: ExclusionData, banned: ReadonlySet<string>): string {
  const output: ExclusionData = { ...data };
  for (const category of ITEM_CATEGORIES) {
    const ids = [...banned]
      .map((key) => key.split(":"))
      .filter(([key]) => key === category)
      .map(([, id]) => Number(id))
      .filter(Number.isInteger)
      .sort((left, right) => left - right);
    output[category] = [...new Set(ids)];
  }
  return stringify(output, { lineWidth: 0 });
}

export function categoryLabel(category: ItemCategory): string {
  return category.replace(/item$/, "").replace(/^./, (character) => character.toUpperCase());
}
