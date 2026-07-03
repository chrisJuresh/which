<script lang="ts">
  import { Archive, ExternalLink } from '@lucide/svelte';
  import type { ArchivePage } from '$lib/types';
  import { formatNumber, initials, relativeDate, statusLabel } from '$lib/format';

  export let page: ArchivePage;
  /** compact = smaller card used in "related" rails */
  export let compact = false;
</script>

<article class="page-card" class:compact>
  <a class="hit" href={`/page/${page.id}`}>
    <div class="media">
      {#if page.image}
        <img src={page.image} alt="" loading="lazy" />
      {:else}
        <div class="fallback-media">{initials(page.title)}</div>
      {/if}
    </div>
    <div class="body">
      <div class="row">
        <span class="type-pill">{page.type}</span>
        <span class="status-pill {page.status}">{statusLabel(page.status)}</span>
      </div>
      <h3>{page.title}</h3>
      {#if !compact}
        <p>{page.description || page.categoryPath.join(' / ')}</p>
      {/if}
    </div>
  </a>
  <div class="actions">
    <span class="ref">#{formatNumber(page.order)}{page.fetchedAt ? ` · ${relativeDate(page.fetchedAt)}` : ''}</span>
    <span class="links">
      {#if page.localHtmlUrl}
        <a class="text-link" href={page.localHtmlUrl}>
          <Archive size={15} /> Open
        </a>
      {/if}
      <a class="text-link" href={page.url} target="_blank" rel="noreferrer noopener">
        <ExternalLink size={15} /> Live
      </a>
    </span>
  </div>
</article>

<style>
  .page-card {
    overflow: hidden;
    display: flex;
    flex-direction: column;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: var(--surface);
    box-shadow: var(--shadow);
    transition: transform 0.12s ease, border-color 0.12s ease;
  }
  .page-card:hover {
    border-color: rgba(11, 112, 111, 0.3);
    transform: translateY(-2px);
  }
  .hit {
    display: flex;
    flex-direction: column;
    flex: 1;
    color: inherit;
    text-decoration: none;
  }
  .media {
    height: 150px;
    flex: none;
  }
  .compact .media {
    height: 108px;
  }
  .media img,
  .media .fallback-media {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    background: #dbe7e4;
  }
  .body {
    display: flex;
    flex-direction: column;
    gap: 9px;
    padding: 13px 13px 6px;
    flex: 1;
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    justify-content: space-between;
  }
  h3 {
    margin: 0;
    font-size: 17px;
    line-height: 1.22;
  }
  p {
    margin: 0;
    color: var(--ink-soft);
    font-size: 14px;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 10px 13px 13px;
    color: var(--ink-soft);
    font-size: 13px;
  }
  .links {
    display: inline-flex;
    gap: 12px;
    align-items: center;
  }
</style>
