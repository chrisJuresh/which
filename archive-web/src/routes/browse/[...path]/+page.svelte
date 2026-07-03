<script lang="ts">
  import { AlertTriangle, CheckCircle2, Clock3, Archive } from '@lucide/svelte';
  import { page as pageStore } from '$app/stores';
  import Breadcrumbs from '$lib/components/Breadcrumbs.svelte';
  import CategoryTree from '$lib/components/CategoryTree.svelte';
  import CategoryCard from '$lib/components/CategoryCard.svelte';
  import PageList from '$lib/components/PageList.svelte';
  import { formatNumber } from '$lib/format';
  import type { PageData } from './$types';

  export let data: PageData;
  $: index = data.archive!;
  $: nodeId = $pageStore.params.path || 'root';
  $: node = index.nodeById.get(nodeId) ?? null;

  $: crumbs = node
    ? node.path.map((_, i) => ({
        label: node!.path[i],
        href: `/browse/${node!.path
          .slice(0, i + 1)
          .map((p) => p.toLowerCase().replace(/[^a-z0-9]+/g, '-'))
          .join('/')}`
      }))
    : [];
</script>

<svelte:head>
  <title>{node ? `${node.label} · Which Archive` : 'Not found'}</title>
</svelte:head>

<div class="page container browse">
  <aside class="rail">
    <div class="rail-inner">
      <a class="rail-all" class:active={nodeId === 'root'} href="/browse">
        All categories <b>{formatNumber(index.root.allPages.length)}</b>
      </a>
      <CategoryTree nodes={index.root.children} currentId={nodeId} />
    </div>
  </aside>

  <div class="main">
    {#if !node}
      <div class="empty-state">
        <h2>Category not found</h2>
        <p>Nothing matches <code>{nodeId}</code>.</p>
        <a class="text-link" href="/browse">Back to all categories</a>
      </div>
    {:else}
      <Breadcrumbs items={crumbs} />
      <header class="head">
        <h1>{node.label}</h1>
        <div class="metrics">
          <div class="metric"><Archive size={16} /><span>Pages</span><strong>{formatNumber(node.allPages.length)}</strong></div>
          <div class="metric good"><CheckCircle2 size={16} /><span>Archived</span><strong>{formatNumber(node.counts.downloaded)}</strong></div>
          <div class="metric wait"><Clock3 size={16} /><span>Pending</span><strong>{formatNumber(node.counts.pending)}</strong></div>
          <div class="metric warn"><AlertTriangle size={16} /><span>Failed</span><strong>{formatNumber(node.counts.failed)}</strong></div>
        </div>
      </header>

      {#if node.children.length}
        <section class="section">
          <div class="section-head">
            <h2>Sections</h2>
            <span class="muted">{formatNumber(node.children.length)}</span>
          </div>
          <div class="card-grid">
            {#each node.children as child (child.id)}
              <CategoryCard node={child} />
            {/each}
          </div>
        </section>
      {/if}

      <section class="section">
        <div class="section-head">
          <h2>Pages</h2>
        </div>
        <PageList pages={node.allPages} />
      </section>
    {/if}
  </div>
</div>

<style>
  .browse {
    display: grid;
    grid-template-columns: 280px minmax(0, 1fr);
    gap: 26px;
    align-items: start;
  }
  .rail-inner {
    position: sticky;
    top: calc(var(--header-h) + 16px);
    max-height: calc(100vh - var(--header-h) - 32px);
    overflow: auto;
    padding: 14px;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: var(--surface-2);
  }
  .rail-all {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 10px;
    padding: 9px 10px;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: #fff;
    color: var(--ink);
    text-decoration: none;
    font-weight: 750;
  }
  .rail-all.active {
    border-color: rgba(11, 112, 111, 0.32);
    background: var(--brand-tint);
    color: var(--brand-dark);
  }
  .rail-all b {
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--brand-tint);
    color: var(--brand-dark);
    font-size: 12px;
  }
  .head {
    margin: 12px 0 4px;
  }
  h1 {
    margin: 6px 0 16px;
    font-size: clamp(28px, 4vw, 44px);
    line-height: 1.02;
  }
  .metrics {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
  }
  .metric {
    display: grid;
    gap: 4px;
    padding: 12px;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: var(--surface);
  }
  .metric span {
    color: var(--ink-soft);
    font-size: 11px;
    font-weight: 750;
    text-transform: uppercase;
  }
  .metric strong {
    font-size: 22px;
    line-height: 1;
  }
  .metric :global(svg) {
    color: var(--brand);
  }
  .metric.good strong {
    color: var(--good);
  }
  .metric.wait strong {
    color: var(--wait);
  }
  .metric.warn :global(svg) {
    color: var(--bad);
  }
  @media (max-width: 900px) {
    .browse {
      grid-template-columns: 1fr;
    }
    .rail-inner {
      position: static;
      max-height: 320px;
    }
    .metrics {
      grid-template-columns: repeat(2, 1fr);
    }
  }
</style>
