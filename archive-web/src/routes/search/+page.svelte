<script lang="ts">
  import { page as pageStore } from '$app/stores';
  import PageList from '$lib/components/PageList.svelte';
  import type { PageData } from './$types';

  export let data: PageData;
  $: index = data.archive!;
  $: q = $pageStore.url.searchParams.get('q') ?? '';
</script>

<svelte:head>
  <title>{q ? `Search: ${q}` : 'Search'} · Which Archive</title>
</svelte:head>

<div class="page container">
  <p class="eyebrow">Search</p>
  <h1>{q ? `Results for “${q}”` : 'Search the archive'}</h1>
  <p class="muted lead">Filter across all {index.data.summary.total.toLocaleString()} pages.</p>

  <PageList pages={index.data.pages} initialQuery={q} />
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
