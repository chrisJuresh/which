import { getArchive } from '$lib/archive';
import type { LayoutLoad } from './$types';

// Pure client-rendered SPA: data lives in /data/archive.json and is loaded at
// runtime, and routes carry dynamic params, so we do not prerender or SSR.
export const ssr = false;
export const prerender = false;

export const load: LayoutLoad = async ({ fetch }) => {
  try {
    return { archive: await getArchive(fetch), loadError: '' };
  } catch (error) {
    return {
      archive: null,
      loadError: error instanceof Error ? error.message : String(error)
    };
  }
};
