export const ITEM_CATEGORIES = [
  "backitem",
  "glassitem",
  "hatitem",
  "pantsitem",
  "shirtsitem",
  "shoesitem",
  "weaponitem",
  "vehicleitem",
  "generalitem",
  "chestitem",
] as const;

export type ItemCategory = (typeof ITEM_CATEGORIES)[number];

export interface CatalogItem {
  id: number;
  category: ItemCategory;
  name: string;
  description: string;
  type: string;
  weaponType: string | null;
  level: number;
  rarity: string;
  gender: string;
  tradeable: boolean;
  sellable: boolean;
  icon: string;
}

export interface Catalog {
  formatVersion: 1;
  revision: number;
  items: CatalogItem[];
  icons: Record<string, string>;
}

export interface ExclusionFile {
  content: string;
  sha: string;
}

export type ExclusionData = Record<string, unknown>;

export interface Filters {
  search: string;
  status: "all" | "banned" | "unbanned" | "changed";
  type: string;
  weaponType: string;
  rarity: string;
  gender: string;
  tradeable: "all" | "yes" | "no";
  sellable: "all" | "yes" | "no";
  minLevel: string;
  maxLevel: string;
}
