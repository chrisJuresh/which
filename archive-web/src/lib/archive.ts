import type { ArchiveData, ArchiveIndex, ArchivePage, CategoryNode } from './types';

/** Stable slug for a category path segment list — must match route params. */
export function pathKey(path: string[]): string {
  return path.map((part) => part.toLowerCase().replace(/[^a-z0-9]+/g, '-')).join('/');
}

function emptyRoot(): CategoryNode {
  return {
    id: 'root',
    label: 'All categories',
    path: [],
    children: [],
    pages: [],
    allPages: [],
    counts: {},
    image: ''
  };
}

function countStatuses(pages: ArchivePage[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const page of pages) counts[page.status] = (counts[page.status] ?? 0) + 1;
  return counts;
}

function bestImage(pages: ArchivePage[]): string {
  return (
    pages.find((page) => page.featured && page.image)?.image ??
    pages.find((page) => page.image)?.image ??
    ''
  );
}

function buildIndex(data: ArchiveData): ArchiveIndex {
  const root = emptyRoot();
  const nodeById = new Map<string, CategoryNode>([['root', root]]);
  const pageById = new Map<string, ArchivePage>();
  const nodeIdByPageId = new Map<string, string>();

  for (const page of data.pages) {
    pageById.set(page.id, page);
    let current = root;
    const path: string[] = [];
    for (const label of page.categoryPath.length ? page.categoryPath : ['Other']) {
      path.push(label);
      const id = pathKey(path);
      let child = nodeById.get(id);
      if (!child) {
        child = {
          id,
          label,
          path: [...path],
          children: [],
          pages: [],
          allPages: [],
          counts: {},
          image: ''
        };
        nodeById.set(id, child);
        current.children.push(child);
      }
      current = child;
    }
    current.pages.push(page);
    nodeIdByPageId.set(page.id, current.id);
  }

  const finish = (node: CategoryNode): ArchivePage[] => {
    node.children.sort((a, b) => a.label.localeCompare(b.label));
    const below = [...node.pages];
    for (const child of node.children) below.push(...finish(child));
    node.allPages = below.sort((a, b) => a.order - b.order);
    node.counts = countStatuses(node.allPages);
    node.image = bestImage(node.allPages);
    return node.allPages;
  };
  finish(root);

  // Fold tiny top-level categories (<=2 archived pages) into one "Other" so the
  // category grid/tree isn't cluttered with single-page sections. The originals
  // stay reachable (nested under Other, still deep-linkable by their own id).
  const MERGE_THRESHOLD = 2;
  const small = root.children.filter((c) => (c.counts.downloaded ?? 0) <= MERGE_THRESHOLD);
  if (small.length > 1) {
    const big = root.children.filter((c) => (c.counts.downloaded ?? 0) > MERGE_THRESHOLD);
    const pages = small.flatMap((c) => c.allPages).sort((a, b) => a.order - b.order);
    const other: CategoryNode = {
      id: '__other',
      label: 'Other',
      path: ['Other'],
      children: [...small].sort((a, b) => a.label.localeCompare(b.label)),
      pages: [],
      allPages: pages,
      counts: countStatuses(pages),
      image: bestImage(pages)
    };
    root.children = [...big, other].sort(
      (a, b) => (b.counts.downloaded ?? 0) - (a.counts.downloaded ?? 0)
    );
    nodeById.set('__other', other);
  }

  return { data, root, nodeById, pageById, nodeIdByPageId };
}

let cache: Promise<ArchiveIndex> | null = null;

/** Load and index archive.json once; cached for the lifetime of the SPA. */
export function getArchive(fetchFn: typeof fetch = fetch): Promise<ArchiveIndex> {
  if (!cache) {
    cache = (async () => {
      const response = await fetchFn('/data/archive.json', { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`Could not load archive data (${response.status})`);
      }
      return buildIndex((await response.json()) as ArchiveData);
    })().catch((error) => {
      cache = null; // allow a retry on the next navigation
      throw error;
    });
  }
  return cache;
}

/** Ancestor category nodes for a page, from top level down to its own. */
export function breadcrumbFor(index: ArchiveIndex, page: ArchivePage): CategoryNode[] {
  const crumbs: CategoryNode[] = [];
  const path: string[] = [];
  for (const label of page.categoryPath.length ? page.categoryPath : ['Other']) {
    path.push(label);
    const node = index.nodeById.get(pathKey(path));
    if (node) crumbs.push(node);
  }
  return crumbs;
}

/** Prev/next sibling pages within a page's own category (ordered). */
export function siblingsFor(
  index: ArchiveIndex,
  page: ArchivePage
): { prev: ArchivePage | null; next: ArchivePage | null; node: CategoryNode | null } {
  const nodeId = index.nodeIdByPageId.get(page.id);
  const node = nodeId ? index.nodeById.get(nodeId) ?? null : null;
  if (!node) return { prev: null, next: null, node: null };
  const list = node.allPages;
  const i = list.findIndex((p) => p.id === page.id);
  return {
    prev: i > 0 ? list[i - 1] : null,
    next: i >= 0 && i < list.length - 1 ? list[i + 1] : null,
    node
  };
}

export type ViewMode = 'all' | 'featured' | 'downloaded' | 'attention';

/** A failed MHTML snapshot is not a real problem — the page downloaded fine. */
function hasRealError(page: ArchivePage): boolean {
  return Boolean(page.error) && !page.error.startsWith('MHTML capture failed');
}

export function matchesMode(page: ArchivePage, mode: ViewMode): boolean {
  if (mode === 'featured') return page.featured;
  if (mode === 'downloaded') return page.status === 'downloaded';
  if (mode === 'attention')
    return page.status === 'failed' || page.status === 'in_progress' || hasRealError(page);
  return true;
}

/**
 * Relevance rank for a search hit: 0 = matched in the title (best), then
 * category, description, type, URL, status. Lower is more relevant.
 */
export function searchRank(page: ArchivePage, value: string): number {
  const needle = value.trim().toLowerCase();
  if (!needle) return 0;
  const fields = [
    page.title,
    page.categoryPath.join(' '),
    page.description,
    page.type,
    page.url,
    page.status
  ];
  for (let i = 0; i < fields.length; i++) {
    if ((fields[i] ?? '').toLowerCase().includes(needle)) return i;
  }
  return fields.length; // matched somewhere odd; sort last
}

export function matchesQuery(page: ArchivePage, value: string): boolean {
  const needle = value.trim().toLowerCase();
  if (!needle) return true;
  return [page.title, page.description, page.url, page.type, page.status, ...page.categoryPath]
    .join(' ')
    .toLowerCase()
    .includes(needle);
}

export function pageSort(a: ArchivePage, b: ArchivePage): number {
  const featuredDelta = Number(b.featured) - Number(a.featured);
  if (featuredDelta !== 0) return featuredDelta;
  const downloadedDelta = Number(b.downloaded) - Number(a.downloaded);
  if (downloadedDelta !== 0) return downloadedDelta;
  return a.order - b.order;
}

/** Filter + sort a page list by the common controls used across routes. */
export function filterPages(
  pages: ArchivePage[],
  opts: { query?: string; mode?: ViewMode; type?: string }
): ArchivePage[] {
  const mode = opts.mode ?? 'all';
  const type = opts.type ?? 'All types';
  const query = (opts.query ?? '').trim();
  const result = pages
    .filter((page) => matchesMode(page, mode))
    .filter((page) => type === 'All types' || page.type === type)
    .filter((page) => matchesQuery(page, query));
  if (query) {
    // Rank by where the query matched (title first), then the usual order.
    return result.sort((a, b) => searchRank(a, query) - searchRank(b, query) || pageSort(a, b));
  }
  return result.sort(pageSort);
}
