<script lang="ts">
  import PageList from '$lib/components/PageList.svelte';
  import { formatNumber } from '$lib/format';
  import type { PageData } from './$types';

  export let data: PageData;
  $: index = data.archive!;
  $: guides = index.data.pages.filter((p) => p.featured);
</script>

<svelte:head>
  <title>Best &amp; buying guides · Which Archive</title>
</svelte:head>

<div class="page container">
  <p class="eyebrow">Guides</p>
  <h1>Best &amp; buying guides</h1>
  <p class="muted lead">{formatNumber(guides.length)} best-buy, top-picks and how-to-buy guides across the archive.</p>
  <PageList pages={guides} />
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
