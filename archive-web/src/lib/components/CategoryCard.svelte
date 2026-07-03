<script lang="ts">
  import type { CategoryNode } from '$lib/types';
  import { formatNumber, initials } from '$lib/format';

  export let node: CategoryNode;
</script>

<a class="category-card" href={`/browse/${node.id}`}>
  <div class="media">
    {#if node.image}
      <img src={node.image} alt="" loading="lazy" />
    {:else}
      <div class="fallback-media">{initials(node.label)}</div>
    {/if}
    {#if node.children.length}
      <span class="badge">{formatNumber(node.children.length)} sections</span>
    {/if}
  </div>
  <div class="body">
    <span class="name">{node.label}</span>
    <small class="muted">
      {formatNumber(node.allPages.length)} pages
      {#if node.counts.downloaded}· {formatNumber(node.counts.downloaded)} archived{/if}
    </small>
  </div>
</a>

<style>
  .category-card {
    overflow: hidden;
    display: grid;
    grid-template-rows: 140px auto;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: var(--surface);
    color: var(--ink);
    text-decoration: none;
    box-shadow: var(--shadow);
    transition: transform 0.12s ease, border-color 0.12s ease;
  }
  .category-card:hover {
    border-color: rgba(11, 112, 111, 0.35);
    transform: translateY(-2px);
  }
  .media {
    position: relative;
  }
  .media img,
  .media .fallback-media {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    background: #dbe7e4;
  }
  .badge {
    position: absolute;
    top: 8px;
    left: 8px;
    padding: 3px 8px;
    border-radius: 999px;
    background: rgba(12, 24, 27, 0.62);
    color: #fff;
    font-size: 11px;
    font-weight: 800;
  }
  .body {
    display: grid;
    gap: 5px;
    padding: 12px 13px 14px;
  }
  .name {
    font-size: 16px;
    font-weight: 850;
    line-height: 1.2;
  }
  small {
    font-size: 13px;
  }
</style>
