export interface ArchivePage {
  id: string;
  order: number;
  url: string;
  finalUrl: string;
  status: string;
  httpStatus: number | null;
  title: string;
  description: string;
  image: string;
  type: string;
  categoryPath: string[];
  featured: boolean;
  downloaded: boolean;
  error: string;
  fetchedAt: string;
  rawHtmlPath: string;
  mhtmlPath: string;
  localHtmlUrl: string;
  localMhtmlUrl: string;
}

export interface ArchiveSummary {
  total: number;
  counts: Record<string, number>;
  types: Record<string, number>;
  featured: number;
  withImages: number;
  withLocalCaptures: number;
}

export interface ArchiveData {
  generatedAt: string;
  sourceCsv: string;
  summary: ArchiveSummary;
  pages: ArchivePage[];
}

export interface CategoryNode {
  id: string;
  label: string;
  path: string[];
  children: CategoryNode[];
  pages: ArchivePage[];
  allPages: ArchivePage[];
  counts: Record<string, number>;
  image: string;
}

/** Everything the UI needs, built once from ArchiveData. */
export interface ArchiveIndex {
  data: ArchiveData;
  root: CategoryNode;
  nodeById: Map<string, CategoryNode>;
  pageById: Map<string, ArchivePage>;
  /** node id of the deepest category a page belongs to, keyed by page id */
  nodeIdByPageId: Map<string, string>;
}
