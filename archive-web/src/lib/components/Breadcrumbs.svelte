<script lang="ts">
  export let items: { label: string; href: string }[] = [];
</script>

<nav class="crumbs" aria-label="Breadcrumb">
  <a href="/">Home</a>
  {#each items as item, i}
    <span class="sep">/</span>
    {#if i < items.length - 1}
      <a href={item.href}>{item.label}</a>
    {:else}
      <span class="current" aria-current="page">{item.label}</span>
    {/if}
  {/each}
</nav>

<style>
  .crumbs {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
    color: var(--ink-soft);
    font-size: 14px;
  }
  a {
    color: var(--ink-soft);
    text-decoration: none;
  }
  a:hover {
    color: var(--brand-dark);
    text-decoration: underline;
  }
  .sep {
    color: #9aa2a7;
  }
  .current {
    color: var(--ink);
    font-weight: 750;
  }
</style>
