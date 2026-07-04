<script lang="ts">
  import { AlertTriangle, CheckCircle2, Search, Star } from '@lucide/svelte';
  import type { ArchivePage } from '$lib/types';
  import { filterPages, type ViewMode } from '$lib/archive';
  import { formatNumber } from '$lib/format';
  import PageCard from './PageCard.svelte';

  export let pages: ArchivePage[] = [];
  export let initialQuery = '';
  export let initialType = 'All types';
  export let showControls = true;

  let query = initialQuery;
  let mode: ViewMode = 'all';
  let typeFilter = initialType;
  let limit = 60;

  // keep controls in sync when the parent changes the incoming query/type (nav)
  let lastInit = initialQuery;
  $: if (initialQuery !== lastInit) {
    lastInit = initialQuery;
    query = initialQuery;
  }
  let lastInitType = initialType;
  $: if (initialType !== lastInitType) {
    lastInitType = initialType;
    typeFilter = initialType;
  }

  $: typeOptions = ['All types', ...Array.from(new Set(pages.map((p) => p.type))).sort()];
  $: if (!typeOptions.includes(typeFilter)) typeFilter = 'All types';
  $: filtered = filterPages(pages, { query, mode, type: typeFilter });
  $: resetKey = `${query}|${mode}|${typeFilter}|${pages.length}`;
  let lastKey = '';
  $: if (resetKey !== lastKey) {
    lastKey = resetKey;
    limit = 60;
  }
  $: shown = filtered.slice(0, limit);
</script>

{#if showControls}
  <div class="controls">
    <label class="search">
      <Search size={18} />
      <input bind:value={query} placeholder="Filter these pages by title, URL, category" />
    </label>

    <div class="segmented" role="group" aria-label="View">
      <button class:active={mode === 'all'} type="button" on:click={() => (mode = 'all')}>All</button>
      <button class:active={mode === 'featured'} type="button" on:click={() => (mode = 'featured')}>
        <Star size={15} /> Best
      </button>
      <button
        class:active={mode === 'downloaded'}
        type="button"
        on:click={() => (mode = 'downloaded')}
      >
        <CheckCircle2 size={15} /> Archived
      </button>
      <button
        class:active={mode === 'attention'}
        type="button"
        on:click={() => (mode = 'attention')}
      >
        <AlertTriangle size={15} /> Issues
      </button>
    </div>

    <select bind:value={typeFilter} aria-label="Page type">
      {#each typeOptions as type}
        <option>{type}</option>
      {/each}
    </select>
  </div>
{/if}

<div class="count muted">{formatNumber(filtered.length)} page{filtered.length === 1 ? '' : 's'}</div>

{#if filtered.length}
  <div class="card-grid">
    {#each shown as page (page.id)}
      <PageCard {page} />
    {/each}
  </div>
  {#if shown.length < filtered.length}
    <button class="show-more" type="button" on:click={() => (limit += 60)}>
      Show more
      <span>{formatNumber(shown.length)} of {formatNumber(filtered.length)}</span>
    </button>
  {/if}
{:else}
  <div class="empty-state">No pages match the current filters.</div>
{/if}

<style>
  .controls {
    position: sticky;
    top: var(--header-h);
    z-index: 2;
    display: grid;
    grid-template-columns: minmax(220px, 1fr) auto 180px;
    gap: 10px;
    align-items: center;
    margin: 0 0 14px;
    padding: 12px;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: rgba(255, 253, 248, 0.92);
    backdrop-filter: blur(8px);
  }
  .search {
    min-height: 42px;
    display: grid;
    grid-template-columns: 20px 1fr;
    gap: 9px;
    align-items: center;
    padding: 0 12px;
    border: 1px solid var(--line-strong);
    border-radius: var(--radius-sm);
    background: #fff;
    color: var(--ink-soft);
  }
  .search input {
    width: 100%;
    min-width: 0;
    border: 0;
    outline: 0;
    background: transparent;
    color: var(--ink);
  }
  .segmented {
    display: inline-grid;
    grid-auto-flow: column;
    gap: 4px;
    padding: 4px;
    border: 1px solid var(--line-strong);
    border-radius: var(--radius-sm);
    background: var(--surface);
  }
  .segmented button {
    min-height: 34px;
    display: inline-flex;
    gap: 6px;
    align-items: center;
    justify-content: center;
    padding: 6px 11px;
    border: 0;
    border-radius: 6px;
    background: transparent;
    color: #4d565c;
    cursor: pointer;
    font-weight: 750;
  }
  .segmented button.active {
    background: var(--brand);
    color: #fff;
  }
  select {
    width: 100%;
    min-height: 42px;
    padding: 0 12px;
    border: 1px solid var(--line-strong);
    border-radius: var(--radius-sm);
    background: #fff;
    color: var(--ink);
  }
  .count {
    margin-bottom: 12px;
    font-size: 14px;
  }
  .show-more {
    display: flex;
    gap: 10px;
    align-items: center;
    justify-content: center;
    width: min(340px, 100%);
    min-height: 46px;
    margin: 20px auto 0;
    padding: 10px 14px;
    border: 0;
    border-radius: var(--radius-sm);
    background: var(--brand);
    color: #fff;
    cursor: pointer;
    font-weight: 850;
  }
  .show-more:hover {
    background: var(--brand-dark);
  }
  .show-more span {
    color: rgba(255, 255, 255, 0.8);
    font-size: 13px;
    font-weight: 700;
  }
  @media (max-width: 860px) {
    .controls {
      grid-template-columns: 1fr;
    }
    .segmented {
      grid-template-columns: repeat(4, 1fr);
      grid-auto-flow: row;
    }
  }
</style>
