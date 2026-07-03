<script lang="ts">
  import { ArrowRight, CheckCircle2, Clock3, Layers3, Star } from '@lucide/svelte';
  import CategoryCard from '$lib/components/CategoryCard.svelte';
  import PageCard from '$lib/components/PageCard.svelte';
  import { pageSort } from '$lib/archive';
  import { formatNumber } from '$lib/format';
  import type { PageData } from './$types';

  export let data: PageData;
  $: index = data.archive!;
  $: summary = index.data.summary;
  $: topCategories = index.root.children;
  $: featured = index.data.pages.filter((p) => p.featured).sort(pageSort).slice(0, 8);
  $: recent = index.data.pages
    .filter((p) => p.status === 'downloaded' && p.fetchedAt)
    .slice()
    .sort((a, b) => b.fetchedAt.localeCompare(a.fetchedAt))
    .slice(0, 8);
</script>

<svelte:head>
  <title>Which Archive</title>
  <meta name="description" content="A local, browsable archive of captured Which pages." />
</svelte:head>

<div class="page">
  <section class="container hero">
    <div class="hero-copy">
      <p class="eyebrow">Local archive</p>
      <h1>Browse the Which archive</h1>
      <p class="lead">
        {formatNumber(summary.total)} pages captured from Which. Follow a link inside any archived
        page and it stays local when we have the target — otherwise it opens the live original.
      </p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="/browse"><Layers3 size={18} /> Browse categories</a>
        <a class="btn" href="/search">Search everything <ArrowRight size={16} /></a>
      </div>
    </div>
    <div class="stat-grid">
      <div class="stat">
        <span>Total</span>
        <strong>{formatNumber(summary.total)}</strong>
      </div>
      <div class="stat good">
        <CheckCircle2 size={16} />
        <span>Archived</span>
        <strong>{formatNumber(summary.counts.downloaded)}</strong>
      </div>
      <div class="stat wait">
        <Clock3 size={16} />
        <span>Pending</span>
        <strong>{formatNumber(summary.counts.pending)}</strong>
      </div>
      <div class="stat accent">
        <Star size={16} />
        <span>Best guides</span>
        <strong>{formatNumber(summary.featured)}</strong>
      </div>
    </div>
  </section>

  <section class="container section">
    <div class="section-head">
      <h2>Browse by category</h2>
      <a class="text-link" href="/browse">All categories <ArrowRight size={15} /></a>
    </div>
    <div class="card-grid">
      {#each topCategories as node (node.id)}
        <CategoryCard {node} />
      {/each}
    </div>
  </section>

  {#if featured.length}
    <section class="container section">
      <div class="section-head">
        <h2>Best &amp; buying guides</h2>
        <span class="muted">{formatNumber(summary.featured)} in total</span>
      </div>
      <div class="card-grid wide">
        {#each featured as page (page.id)}
          <PageCard {page} />
        {/each}
      </div>
    </section>
  {/if}

  {#if recent.length}
    <section class="container section">
      <div class="section-head">
        <h2>Recently archived</h2>
      </div>
      <div class="card-grid">
        {#each recent as page (page.id)}
          <PageCard {page} compact />
        {/each}
      </div>
    </section>
  {/if}
</div>

<style>
  .hero {
    display: grid;
    grid-template-columns: minmax(0, 1.3fr) minmax(320px, 1fr);
    gap: 32px;
    align-items: center;
    padding-top: 12px;
  }
  h1 {
    margin: 0 0 12px;
    font-size: clamp(34px, 5vw, 56px);
    line-height: 1;
  }
  .lead {
    margin: 0 0 20px;
    max-width: 54ch;
    color: var(--ink-soft);
    font-size: 17px;
  }
  .hero-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }
  .stat-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
  .stat {
    display: grid;
    gap: 4px;
    padding: 16px;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: var(--surface);
    box-shadow: var(--shadow);
  }
  .stat span {
    color: var(--ink-soft);
    font-size: 12px;
    font-weight: 750;
    text-transform: uppercase;
  }
  .stat strong {
    font-size: 30px;
    line-height: 1;
  }
  .stat :global(svg) {
    color: var(--brand);
  }
  .stat.good strong {
    color: var(--good);
  }
  .stat.wait strong {
    color: var(--wait);
  }
  .stat.accent strong {
    color: var(--blue);
  }
  @media (max-width: 860px) {
    .hero {
      grid-template-columns: 1fr;
    }
  }
</style>
