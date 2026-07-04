<script lang="ts">
  import { onMount } from 'svelte';
  import { ArrowRight, CheckCircle2, Layers3, Star, Tag } from '@lucide/svelte';
  import CategoryCard from '$lib/components/CategoryCard.svelte';
  import PageCard from '$lib/components/PageCard.svelte';
  import type { ArchivePage } from '$lib/types';
  import { formatNumber } from '$lib/format';
  import type { PageData } from './$types';

  export let data: PageData;
  $: index = data.archive!;
  $: summary = index.data.summary;

  // Categories, most-archived first.
  $: topCategories = [...index.root.children].sort(
    (a, b) => (b.counts.downloaded ?? 0) - (a.counts.downloaded ?? 0)
  );

  // Page types, largest first, for "Browse by type".
  $: typeEntries = Object.entries(summary.types)
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1]);

  function sample(arr: ArchivePage[], n: number): ArchivePage[] {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a.slice(0, n);
  }

  // Reshuffled on every page load (i.e. every refresh).
  let featured: ArchivePage[] = [];
  onMount(() => {
    featured = sample(
      index.data.pages.filter((p) => p.featured && p.downloaded),
      8
    );
  });
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
      <div class="stat good">
        <CheckCircle2 size={16} />
        <span>Pages archived</span>
        <strong>{formatNumber(summary.counts.downloaded ?? summary.total)}</strong>
      </div>
      <div class="stat">
        <Layers3 size={16} />
        <span>Categories</span>
        <strong>{formatNumber(topCategories.length)}</strong>
      </div>
      <div class="stat accent">
        <Star size={16} />
        <span>Best &amp; buying guides</span>
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

  <section class="container section">
    <div class="section-head">
      <h2>Best &amp; buying guides</h2>
      <span class="muted">{formatNumber(summary.featured)} in total · shuffled</span>
    </div>
    <div class="card-grid wide">
      {#each featured as page (page.id)}
        <PageCard {page} />
      {/each}
      <a class="viewall" href="/guides">
        <Star size={22} />
        <strong>View all guides</strong>
        <span>{formatNumber(summary.featured)} best &amp; buying guides</span>
        <span class="go">Open <ArrowRight size={15} /></span>
      </a>
    </div>
  </section>

  <section class="container section">
    <div class="section-head">
      <h2>Browse by type</h2>
      <span class="muted">{formatNumber(typeEntries.length)} kinds of page</span>
    </div>
    <div class="type-grid">
      {#each typeEntries as [type, n] (type)}
        <a class="type-card" href={`/search?type=${encodeURIComponent(type)}`}>
          <Tag size={16} />
          <span class="name">{type}</span>
          <b>{formatNumber(n)}</b>
        </a>
      {/each}
    </div>
  </section>
</div>

<style>
  .hero {
    display: grid;
    grid-template-columns: minmax(0, 1.3fr) minmax(300px, 1fr);
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
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
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
    font-size: 28px;
    line-height: 1;
  }
  .stat :global(svg) {
    color: var(--brand);
  }
  .stat.good strong {
    color: var(--good);
  }
  .stat.accent strong {
    color: var(--blue);
  }

  .viewall {
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 8px;
    padding: 20px;
    border: 1px dashed rgba(11, 112, 111, 0.5);
    border-radius: var(--radius);
    background: var(--brand-tint);
    color: var(--brand-dark);
    text-decoration: none;
    text-align: center;
    min-height: 150px;
  }
  .viewall:hover {
    background: rgba(11, 112, 111, 0.16);
  }
  .viewall :global(svg) {
    margin: 0 auto;
  }
  .viewall strong {
    font-size: 18px;
  }
  .viewall span {
    color: var(--ink-soft);
    font-size: 13px;
  }
  .viewall .go {
    display: inline-flex;
    gap: 5px;
    align-items: center;
    justify-content: center;
    margin-top: 4px;
    color: var(--brand-dark);
    font-weight: 800;
  }

  .type-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 12px;
  }
  .type-card {
    display: grid;
    grid-template-columns: 20px 1fr auto;
    gap: 10px;
    align-items: center;
    padding: 14px 16px;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    background: var(--surface);
    color: var(--ink);
    text-decoration: none;
  }
  .type-card:hover {
    border-color: rgba(11, 112, 111, 0.4);
    background: var(--surface-2);
  }
  .type-card :global(svg) {
    color: var(--brand);
  }
  .type-card .name {
    font-weight: 750;
  }
  .type-card b {
    color: var(--brand-dark);
    font-variant-numeric: tabular-nums;
  }

  @media (max-width: 860px) {
    .hero {
      grid-template-columns: 1fr;
    }
  }
</style>
