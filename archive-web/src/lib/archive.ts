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

export function matchesMode(page: ArchivePage, mode: ViewMode): boolean {
  if (mode === 'featured') return page.featured;
  if (mode === 'downloaded') return page.status === 'downloaded';
  if (mode === 'attention')
    return page.status === 'failed' || page.status === 'in_progress' || Boolean(page.error);
  return true;
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
  const query = opts.query ?? '';
  return pages
    .filter((page) => matchesMode(page, mode))
    .filter((page) => type === 'All types' || page.type === type)
    .filter((page) => matchesQuery(page, query))
    .sort(pageSort);
}
