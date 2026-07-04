<script lang="ts">
  import { page as pageStore } from '$app/stores';
  import PageList from '$lib/components/PageList.svelte';
  import type { PageData } from './$types';

  export let data: PageData;
  $: index = data.archive!;
  $: q = $pageStore.url.searchParams.get('q') ?? '';
  $: type = $pageStore.url.searchParams.get('type') ?? 'All types';

  $: heading = q
    ? `Results for “${q}”`
    : type !== 'All types'
      ? type
      : 'Search the archive';
</script>

<svelte:head>
  <title>{q || (type !== 'All types' ? type : 'Search')} · Which Archive</title>
</svelte:head>

<div class="page container">
  <p class="eyebrow">{type !== 'All types' && !q ? 'Browse by type' : 'Search'}</p>
  <h1>{heading}</h1>
  <p class="muted lead">Filter across all {index.data.summary.total.toLocaleString()} pages.</p>

  <PageList pages={index.data.pages} initialQuery={q} initialType={type} />
</div>

<style>
  h1 {
    margin: 4px 0 8px;
    font-size: clamp(26px, 4vw, 40px);
    line-height: 1.05;
  }
  .lead {
    margin: 0 0 20px;
    font-size: 16px;
  }
</style>
