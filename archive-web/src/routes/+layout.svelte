<script lang="ts">
  import '$lib/styles.css';
  import { AlertTriangle, Layers3, Search } from '@lucide/svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { formatNumber } from '$lib/format';
  import type { LayoutData } from './$types';

  export let data: LayoutData;

  let term = '';
  $: term = $page.url.pathname === '/search' ? ($page.url.searchParams.get('q') ?? '') : term;

  function submitSearch(event: Event) {
    event.preventDefault();
    const q = term.trim();
    goto(q ? `/search?q=${encodeURIComponent(q)}` : '/search');
  }
</script>

<a class="skip" href="#main">Skip to content</a>

<header class="topbar">
  <div class="container bar">
    <a class="brand" href="/">
      <span class="mark">W</span>
      <span class="brand-text">
        <strong>Which Archive</strong>
        {#if data.archive}
          <small>{formatNumber(data.archive.data.summary.total)} pages</small>
        {/if}
      </span>
    </a>

    <form class="search" on:submit={submitSearch} role="search">
      <Search size={18} />
      <input
        bind:value={term}
        placeholder="Search the whole archive"
        aria-label="Search the archive"
      />
    </form>

    <nav class="links">
      <a href="/" class:active={$page.url.pathname === '/'}>Home</a>
      <a href="/browse" class:active={$page.url.pathname.startsWith('/browse')}>
        <Layers3 size={16} /> Browse
      </a>
    </nav>
  </div>
</header>

<main id="main">
  {#if data.loadError}
    <div class="container">
      <div class="state-screen">
        <AlertTriangle size={34} color="var(--bad)" />
        <h1>Archive data not found</h1>
        <p>{data.loadError}</p>
        <p class="muted">
          Generate it first from the project root:<br />
          <code>uv run python export_archive_data.py</code><br />
          or just run <code>npm run dev</code> in <code>archive-web/</code> (it exports for you).
        </p>
      </div>
    </div>
  {:else}
    <slot />
  {/if}
</main>

<style>
  .skip {
    position: absolute;
    left: -9999px;
    top: 0;
    z-index: 20;
    padding: 10px 14px;
    background: var(--brand);
    color: #fff;
    border-radius: 0 0 8px 0;
  }
  .skip:focus {
    left: 0;
  }
  .topbar {
    position: sticky;
    top: 0;
    z-index: 10;
    height: var(--header-h);
    border-bottom: 1px solid var(--line);
    background: rgba(255, 253, 247, 0.9);
    backdrop-filter: blur(10px);
  }
  .bar {
    height: 100%;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: 16px;
    align-items: center;
  }
  .brand {
    display: inline-flex;
    gap: 10px;
    align-items: center;
    text-decoration: none;
    color: var(--ink);
  }
  .mark {
    display: grid;
    place-items: center;
    width: 36px;
    height: 36px;
    border-radius: 8px;
    background: var(--brand);
    color: #fff;
    font-size: 19px;
    font-weight: 900;
  }
  .brand-text {
    display: grid;
    line-height: 1.1;
  }
  .brand-text strong {
    font-size: 16px;
  }
  .brand-text small {
    color: var(--ink-soft);
    font-size: 12px;
  }
  .search {
    display: grid;
    grid-template-columns: 20px 1fr;
    gap: 9px;
    align-items: center;
    max-width: 520px;
    width: 100%;
    justify-self: center;
    min-height: 40px;
    padding: 0 12px;
    border: 1px solid var(--line-strong);
    border-radius: 999px;
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
  .links {
    display: inline-flex;
    gap: 4px;
    align-items: center;
  }
  .links a {
    display: inline-flex;
    gap: 6px;
    align-items: center;
    padding: 8px 12px;
    border-radius: var(--radius-sm);
    color: var(--ink);
    text-decoration: none;
    font-weight: 750;
  }
  .links a:hover {
    background: var(--brand-tint);
    color: var(--brand-dark);
  }
  .links a.active {
    background: var(--brand-tint);
    color: var(--brand-dark);
  }
  @media (max-width: 720px) {
    .topbar {
      height: auto;
      padding: 10px 0;
    }
    .bar {
      grid-template-columns: 1fr auto;
      row-gap: 10px;
    }
    .search {
      grid-column: 1 / -1;
      order: 3;
      max-width: none;
    }
    .brand-text small {
      display: none;
    }
  }
</style>
