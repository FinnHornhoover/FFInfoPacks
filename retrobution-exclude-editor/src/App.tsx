import { useMemo, useState } from "react";
import { fetchExclusions, submitExclusions } from "./api";
import { decryptCatalog, signSubmission } from "./crypto";
import {
  bannedKeys,
  categoryLabel,
  itemKey,
  parseExclusions,
  serializeExclusions,
} from "./exclusions";
import type { Catalog, CatalogItem, ExclusionData, Filters } from "./types";

const EMPTY_FILTERS: Filters = {
  search: "",
  status: "all",
  type: "",
  weaponType: "",
  rarity: "",
  gender: "",
  tradeable: "all",
  sellable: "all",
  minLevel: "",
  maxLevel: "",
};
const PAGE_SIZE = 120;

function optionValues(items: CatalogItem[], field: "type" | "weaponType" | "rarity" | "gender") {
  return [...new Set(items.map((item) => item[field]).filter((value): value is string => Boolean(value)))].sort();
}

function ItemCard({
  item,
  banned,
  changed,
  icon,
  selected,
  onSelect,
}: {
  item: CatalogItem;
  banned: boolean;
  changed: boolean;
  icon: string | undefined;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      className={`item-card ${banned ? "is-banned" : ""} ${selected ? "is-selected" : ""}`}
      onClick={onSelect}
      type="button"
    >
      <div className="icon-frame">
        {icon ? <img src={`data:image/png;base64,${icon}`} alt="" loading="lazy" /> : <span>?</span>}
      </div>
      <div className="item-card-copy">
        <strong>{item.name || "Unnamed item"}</strong>
        <span>{item.type}{item.weaponType && item.weaponType !== "None" ? ` · ${item.weaponType}` : ""}</span>
        <span>Lv {item.level} · {item.rarity} · ID {item.id}</span>
      </div>
      <span className="status-pill">{banned ? "Banned" : "Allowed"}{changed ? " *" : ""}</span>
    </button>
  );
}

export function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [passphrase, setPassphrase] = useState("");
  const [unlockKey, setUnlockKey] = useState("");
  const [exclusionData, setExclusionData] = useState<ExclusionData | null>(null);
  const [sourceSha, setSourceSha] = useState("");
  const [originalBanned, setOriginalBanned] = useState<Set<string>>(new Set());
  const [currentBanned, setCurrentBanned] = useState<Set<string>>(new Set());
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function unlock(event: React.FormEvent) {
    event.preventDefault();
    if (!passphrase) return;
    setBusy(true);
    setError("");
    setMessage("Decrypting catalog…");
    try {
      const encrypted = await fetch("/catalog.enc").then((response) => {
        if (!response.ok) throw new Error("The encrypted catalog has not been deployed.");
        return response.arrayBuffer();
      });
      const decrypted = await decryptCatalog(encrypted, passphrase);
      setMessage("Loading current exclusions…");
      const exclusionFile = await fetchExclusions();
      const parsed = parseExclusions(exclusionFile.content);
      const banned = bannedKeys(parsed);
      setCatalog(decrypted);
      setUnlockKey(passphrase);
      setPassphrase("");
      setExclusionData(parsed);
      setSourceSha(exclusionFile.sha);
      setOriginalBanned(new Set(banned));
      setCurrentBanned(new Set(banned));
      setMessage("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unlock failed.");
      setMessage("");
    } finally {
      setBusy(false);
    }
  }

  function lock() {
    setCatalog(null);
    setUnlockKey("");
    setExclusionData(null);
    setSourceSha("");
    setOriginalBanned(new Set());
    setCurrentBanned(new Set());
    setSelectedKey(null);
    setFilters(EMPTY_FILTERS);
    setPage(1);
    setMessage("");
    setError("");
  }

  function updateFilter<Key extends keyof Filters>(key: Key, value: Filters[Key]) {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  }

  function toggleItem(item: CatalogItem) {
    const key = itemKey(item);
    setCurrentBanned((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const changedKeys = useMemo(() => {
    const changed = new Set<string>();
    for (const key of new Set([...originalBanned, ...currentBanned])) {
      if (originalBanned.has(key) !== currentBanned.has(key)) changed.add(key);
    }
    return changed;
  }, [originalBanned, currentBanned]);

  const filteredItems = useMemo(() => {
    if (!catalog) return [];
    const query = filters.search.trim().toLocaleLowerCase();
    const minLevel = filters.minLevel === "" ? Number.NEGATIVE_INFINITY : Number(filters.minLevel);
    const maxLevel = filters.maxLevel === "" ? Number.POSITIVE_INFINITY : Number(filters.maxLevel);
    return catalog.items.filter((item) => {
      const key = itemKey(item);
      const banned = currentBanned.has(key);
      if (query && !item.name.toLocaleLowerCase().includes(query) && !String(item.id).includes(query)) return false;
      if (filters.status === "banned" && !banned) return false;
      if (filters.status === "unbanned" && banned) return false;
      if (filters.status === "changed" && !changedKeys.has(key)) return false;
      if (filters.type && item.type !== filters.type) return false;
      if (filters.weaponType && item.weaponType !== filters.weaponType) return false;
      if (filters.rarity && item.rarity !== filters.rarity) return false;
      if (filters.gender && item.gender !== filters.gender) return false;
      if (filters.tradeable !== "all" && item.tradeable !== (filters.tradeable === "yes")) return false;
      if (filters.sellable !== "all" && item.sellable !== (filters.sellable === "yes")) return false;
      return item.level >= minLevel && item.level <= maxLevel;
    });
  }, [catalog, changedKeys, currentBanned, filters]);

  const selectedItem = useMemo(
    () => catalog?.items.find((item) => itemKey(item) === selectedKey) ?? null,
    [catalog, selectedKey],
  );
  const visibleItems = filteredItems.slice(0, page * PAGE_SIZE);

  async function submit() {
    if (!exclusionData || changedKeys.size === 0) return;
    if (!window.confirm(`Commit ${changedKeys.size} item exclusion change(s) directly to main?`)) return;
    setBusy(true);
    setError("");
    setMessage("Committing exclusions…");
    try {
      const content = serializeExclusions(exclusionData, currentBanned);
      const timestamp = new Date().toISOString();
      const signature = await signSubmission(unlockKey, timestamp, sourceSha, content);
      const result = await submitExclusions(content, sourceSha, signature, timestamp);
      const parsed = parseExclusions(content);
      setExclusionData(parsed);
      setSourceSha(result.contentSha);
      setOriginalBanned(new Set(currentBanned));
      setMessage(`Committed successfully: ${result.commitSha.slice(0, 8)}`);
    } catch (reason) {
      setError(
        reason instanceof Error && reason.name === "ConflictError"
          ? "The exclusion file changed while you were editing. Lock and unlock again to load the latest version."
          : reason instanceof Error
            ? reason.message
            : "Commit failed.",
      );
      setMessage("");
    } finally {
      setBusy(false);
    }
  }

  if (!catalog) {
    return (
      <main className="unlock-layout">
        <section className="unlock-card">
          <div className="eyebrow">Restricted tool</div>
          <h1>Retrobution exclusions</h1>
          <p>Enter the editor key to decrypt item information and icons. The key is held only for this tab.</p>
          <form onSubmit={unlock}>
            <label htmlFor="editor-key">Editor key</label>
            <input
              id="editor-key"
              type="password"
              autoComplete="off"
              value={passphrase}
              onChange={(event) => setPassphrase(event.target.value)}
              disabled={busy}
              autoFocus
            />
            <button className="primary" type="submit" disabled={busy || !passphrase}>
              {busy ? "Unlocking…" : "Unlock editor"}
            </button>
          </form>
          {(message || error) && <p className={error ? "notice error" : "notice"}>{error || message}</p>}
        </section>
      </main>
    );
  }

  const types = optionValues(catalog.items, "type");
  const weaponTypes = optionValues(catalog.items, "weaponType").filter((value) => value !== "None");
  const rarities = optionValues(catalog.items, "rarity");
  const genders = optionValues(catalog.items, "gender");

  return (
    <div className="app-shell">
      <header>
        <div>
          <div className="eyebrow">Retrobution r{catalog.revision}</div>
          <h1>Item exclusions</h1>
        </div>
        <div className="header-actions">
          <span>{currentBanned.size} banned · {changedKeys.size} changed</span>
          <button className="secondary" type="button" onClick={lock}>Lock</button>
          <button className="primary" type="button" onClick={submit} disabled={busy || changedKeys.size === 0}>
            {busy ? "Submitting…" : "Submit changes"}
          </button>
        </div>
      </header>

      <div className="workspace">
        <aside className="filters">
          <h2>Filters</h2>
          <label>Search<input value={filters.search} onChange={(e) => updateFilter("search", e.target.value)} placeholder="Name or ID" /></label>
          <label>Status<select value={filters.status} onChange={(e) => updateFilter("status", e.target.value as Filters["status"])}><option value="all">All</option><option value="banned">Banned</option><option value="unbanned">Unbanned</option><option value="changed">Changed</option></select></label>
          <label>Item type<select value={filters.type} onChange={(e) => updateFilter("type", e.target.value)}><option value="">All</option>{types.map((value) => <option key={value}>{value}</option>)}</select></label>
          <label>Weapon subtype<select value={filters.weaponType} onChange={(e) => updateFilter("weaponType", e.target.value)}><option value="">All</option>{weaponTypes.map((value) => <option key={value}>{value}</option>)}</select></label>
          <label>Rarity<select value={filters.rarity} onChange={(e) => updateFilter("rarity", e.target.value)}><option value="">All</option>{rarities.map((value) => <option key={value}>{value}</option>)}</select></label>
          <label>Gender<select value={filters.gender} onChange={(e) => updateFilter("gender", e.target.value)}><option value="">All</option>{genders.map((value) => <option key={value}>{value}</option>)}</select></label>
          <div className="level-row">
            <label>Min level<input type="number" min="0" value={filters.minLevel} onChange={(e) => updateFilter("minLevel", e.target.value)} /></label>
            <label>Max level<input type="number" min="0" value={filters.maxLevel} onChange={(e) => updateFilter("maxLevel", e.target.value)} /></label>
          </div>
          <label>Tradeable<select value={filters.tradeable} onChange={(e) => updateFilter("tradeable", e.target.value as Filters["tradeable"])}><option value="all">All</option><option value="yes">Yes</option><option value="no">No</option></select></label>
          <label>Sellable<select value={filters.sellable} onChange={(e) => updateFilter("sellable", e.target.value as Filters["sellable"])}><option value="all">All</option><option value="yes">Yes</option><option value="no">No</option></select></label>
          <button className="text-button" type="button" onClick={() => { setFilters(EMPTY_FILTERS); setPage(1); }}>Clear filters</button>
        </aside>

        <main className="catalog">
          {(message || error) && <div className={error ? "banner error" : "banner"}>{error || message}</div>}
          <div className="results-heading"><strong>{filteredItems.length.toLocaleString()} items</strong><span>Red items are banned</span></div>
          <div className="item-grid">
            {visibleItems.map((item) => {
              const key = itemKey(item);
              return <ItemCard key={key} item={item} banned={currentBanned.has(key)} changed={changedKeys.has(key)} icon={catalog.icons[item.icon]} selected={selectedKey === key} onSelect={() => setSelectedKey(key)} />;
            })}
          </div>
          {visibleItems.length < filteredItems.length && <button className="load-more" type="button" onClick={() => setPage((value) => value + 1)}>Show more</button>}
        </main>

        <aside className="details">
          {selectedItem ? (
            <>
              <div className="detail-icon">{catalog.icons[selectedItem.icon] && <img src={`data:image/png;base64,${catalog.icons[selectedItem.icon]}`} alt="" />}</div>
              <div className="eyebrow">{categoryLabel(selectedItem.category)} · ID {selectedItem.id}</div>
              <h2>{selectedItem.name || "Unnamed item"}</h2>
              {selectedItem.description && <p className="item-description">{selectedItem.description}</p>}
              <dl>
                <div><dt>Type</dt><dd>{selectedItem.type}{selectedItem.weaponType && selectedItem.weaponType !== "None" ? ` / ${selectedItem.weaponType}` : ""}</dd></div>
                <div><dt>Level</dt><dd>{selectedItem.level}</dd></div>
                <div><dt>Rarity</dt><dd>{selectedItem.rarity}</dd></div>
                <div><dt>Gender</dt><dd>{selectedItem.gender}</dd></div>
                <div><dt>Tradeable</dt><dd>{selectedItem.tradeable ? "Yes" : "No"}</dd></div>
                <div><dt>Sellable</dt><dd>{selectedItem.sellable ? "Yes" : "No"}</dd></div>
              </dl>
              <button className={currentBanned.has(itemKey(selectedItem)) ? "allow-button" : "ban-button"} type="button" onClick={() => toggleItem(selectedItem)}>
                {currentBanned.has(itemKey(selectedItem)) ? "Unban item" : "Ban item"}
              </button>
              {changedKeys.has(itemKey(selectedItem)) && <button className="text-button" type="button" onClick={() => toggleItem(selectedItem)}>Undo this change</button>}
            </>
          ) : <p className="empty-detail">Select an item to inspect or change its status.</p>}
        </aside>
      </div>
    </div>
  );
}
