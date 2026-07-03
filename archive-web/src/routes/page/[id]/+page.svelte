<script lang="ts">
  import { Archive, ArrowLeft, ArrowRight, ExternalLink, FileText } from '@lucide/svelte';
  import { page as pageStore } from '$app/stores';
  import Breadcrumbs from '$lib/components/Breadcrumbs.svelte';
  import PageCard from '$lib/components/PageCard.svelte';
  import { breadcrumbFor, siblingsFor } from '$lib/archive';
  import { formatNumber, initials, relativeDate, statusLabel } from '$lib/format';
  import type { PageData } from './$types';

  export let data: PageData;
  $: index = data.archive!;
  $: id = $pageStore.params.id;
  $: entry = index.pageById.get(id) ?? null;

  $: crumbs = entry
    ? breadcrumbFor(index, entry).map((n) => ({ label: n.label, href: `/browse/${n.id}` }))
    : [];
  $: siblings = entry ? siblingsFor(index, entry) : { prev: null, next: null, node: null };
  $: related = siblings.node
    ? siblings.node.allPages.filter((p) => p.id !== entry?.id).slice(0, 8)
    : [];
</script>

<svelte:head>
  <title>{entry ? `${entry.title} · Which Archive` : 'Not found'}</title>
</svelte:head>

<div class="page container">
  {#if !entry}
    <div class="empty-state">
      <h2>Page not found</h2>
      <p>No archived page has id <code>{id}</code>.</p>
      <a class="text-link" href="/browse">Browse the archive</a>
    </div>
  {:else}
    <Breadcrumbs items={crumbs} />

    <article class="detail">
      <div class="lead">
        <div class="pills">
          <span class="type-pill">{entry.type}</span>
          <span class="status-pill {entry.status}">{statusLabel(entry.status)}</span>
          {#if entry.featured}<span class="type-pill">★ Best guide</span>{/if}
        </div>
        <h1>{entry.title}</h1>
        {#if entry.description}<p class="desc">{entry.description}</p>{/if}

        <div class="actions">
          {#if entry.localHtmlUrl}
            <a class="btn btn-primary" href={entry.localHtmlUrl}>
              <Archive size={18} /> Open archived page
            </a>
          {/if}
          {#if entry.localMhtmlUrl}
            <a class="btn" href={entry.localMhtmlUrl} target="_blank" rel="noreferrer noopener">
              <FileText size={16} /> MHTML snapshot
            </a>
          {/if}
          <a class="btn" href={entry.url} target="_blank" rel="noreferrer noopener">
            <ExternalLink size={16} /> View live original
          </a>
        </div>

        {#if entry.error}<div class="error-note">{entry.error}</div>{/if}

        <dl class="meta">
          <div><dt>Status</dt><dd>{statusLabel(entry.status)}{entry.httpStatus ? ` (HTTP ${entry.httpStatus})` : ''}</dd></div>
          {#if entry.fetchedAt}<div><dt>Captured</dt><dd>{relativeDate(entry.fetchedAt)}</dd></div>{/if}
          <div><dt>Category</dt><dd>{entry.categoryPath.join(' / ') || 'Other'}</dd></div>
          <div class="wide"><dt>Original URL</dt><dd><a class="text-link" href={entry.url} target="_blank" rel="noreferrer noopener">{entry.url}</a></dd></div>
          {#if entry.finalUrl && entry.finalUrl !== entry.url}
            <div class="wide"><dt>Resolved URL</dt><dd>{entry.finalUrl}</dd></div>
          {/if}
        </dl>
      </div>

      <div class="poster">
        {#if entry.image}
          <img src={entry.image} alt="" />
        {:else}
          <div class="fallback-media">{initials(entry.title)}</div>
        {/if}
      </div>
    </article>

    <nav class="prevnext">
      {#if siblings.prev}
        <a class="pn" href={`/page/${siblings.prev.id}`}>
          <ArrowLeft size={16} />
          <span><small>Previous</small>{siblings.prev.title}</span>
        </a>
      {:else}<span></span>{/if}
      {#if siblings.next}
        <a class="pn next" href={`/page/${siblings.next.id}`}>
          <span><small>Next</small>{siblings.next.title}</span>
          <ArrowRight size={16} />
        </a>
      {/if}
    </nav>

    {#if related.length}
      <section class="section">
        <div class="section-head">
          <h2>More in {siblings.node?.label}</h2>
          <a class="text-link" href={`/browse/${siblings.node?.id}`}>See all <ArrowRight size={15} /></a>
        </div>
        <div class="card-grid">
          {#each related as rel (rel.id)}
            <PageCard page={rel} compact />
          {/each}
        </div>
      </section>
    {/if}
  {/if}
</div>

<style>
  .detail {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 300px;
    gap: 28px;
    align-items: start;
    margin-top: 14px;
  }
  .pills {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 14px;
  }
  h1 {
    margin: 0 0 12px;
    font-size: clamp(28px, 4vw, 44px);
    line-height: 1.03;
  }
  .desc {
    margin: 0 0 18px;
    max-width: 62ch;
    color: var(--ink-soft);
    font-size: 17px;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 18px;
  }
  .error-note {
    margin-bottom: 16px;
    padding: 10px 12px;
    border-radius: var(--radius-sm);
    background: rgba(189, 74, 56, 0.08);
    color: #9d3e2f;
    font-size: 14px;
  }
  .meta {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px 20px;
    margin: 0;
    padding: 16px;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: var(--surface);
  }
  .meta .wide {
    grid-column: 1 / -1;
  }
  .meta dt {
    color: var(--ink-soft);
    font-size: 12px;
    font-weight: 750;
    text-transform: uppercase;
  }
  .meta dd {
    margin: 3px 0 0;
    word-break: break-word;
  }
  .poster {
    overflow: hidden;
    border-radius: var(--radius);
    border: 1px solid var(--line);
    aspect-ratio: 4 / 3;
    box-shadow: var(--shadow);
  }
  .poster img,
  .poster .fallback-media {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .prevnext {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-top: 26px;
  }
  .pn {
    display: flex;
    gap: 10px;
    align-items: center;
    padding: 12px 14px;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: var(--surface);
    color: var(--ink);
    text-decoration: none;
  }
  .pn:hover {
    border-color: rgba(11, 112, 111, 0.35);
  }
  .pn.next {
    justify-content: flex-end;
    text-align: right;
  }
  .pn span {
    display: grid;
    line-height: 1.25;
    overflow: hidden;
  }
  .pn small {
    color: var(--ink-soft);
    font-size: 12px;
    text-transform: uppercase;
    font-weight: 750;
  }
  @media (max-width: 820px) {
    .detail {
      grid-template-columns: 1fr;
    }
    .poster {
      order: -1;
      max-height: 260px;
    }
    .prevnext {
      grid-template-columns: 1fr;
    }
  }
</style>
