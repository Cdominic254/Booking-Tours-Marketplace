// Side-by-side comparison selections. The list holds only type + slug, so a
// stored selection always resolves against the live catalogue instead of
// freezing prices or names that later change.
const STORAGE_KEY = 'kenya-tours-compare';
export const COMPARE_EVENT = 'kenya-compare-changed';
export const COMPARE_LIMIT = 4;
const LISTING_TYPES = ['tour', 'property'];

function usable(item) {
  return Boolean(item) && LISTING_TYPES.includes(item.type) && typeof item.slug === 'string' && item.slug !== '';
}

export function readCompare() {
  try {
    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]');
    if (!Array.isArray(stored)) return [];
    const seen = new Set();
    return stored.filter((item) => {
      if (!usable(item)) return false;
      const key = `${item.type}:${item.slug}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    }).slice(0, COMPARE_LIMIT);
  } catch {
    return [];
  }
}

function writeCompare(items) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, COMPARE_LIMIT)));
  } catch {
    // Private browsing can block storage; the page still works for this visit.
  }
  window.dispatchEvent(new Event(COMPARE_EVENT));
}

export function replaceCompare(items) {
  writeCompare(items.filter(usable).slice(0, COMPARE_LIMIT));
}

export function compareKey(item) {
  return `${item.type}:${item.slug}`;
}

export function removeCompare(type, slug) {
  writeCompare(readCompare().filter((item) => !(item.type === type && item.slug === slug)));
}

export function toggleCompare(type, slug) {
  const items = readCompare();
  const index = items.findIndex((item) => item.type === type && item.slug === slug);
  if (index >= 0) {
    items.splice(index, 1);
    writeCompare(items);
    return { selected: false, full: false };
  }
  if (items.length >= COMPARE_LIMIT) {
    return { selected: false, full: true };
  }
  items.push({ type, slug });
  writeCompare(items);
  return { selected: true, full: false };
}

export function clearCompare() {
  writeCompare([]);
}

export function isCompared(items, type, slug) {
  return (items || []).some((item) => item.type === type && item.slug === slug);
}

export function parseCompareParam(value) {
  if (!value) return [];
  const seen = new Set();
  const items = [];
  value.split(',').forEach((entry) => {
    const [type, ...rest] = String(entry).trim().split(':');
    const slug = rest.join(':').trim();
    if (!LISTING_TYPES.includes(type) || !slug) return;
    const key = `${type}:${slug}`;
    if (seen.has(key) || items.length >= COMPARE_LIMIT) return;
    seen.add(key);
    items.push({ type, slug });
  });
  return items;
}

export function compareHref(items) {
  if (!items || items.length === 0) return '/compare.html';
  return `/compare.html?items=${items.map((item) => `${item.type}:${item.slug}`).join(',')}`;
}
