<script lang="ts">
  import { ChevronRight } from '@lucide/svelte';
  import type { CategoryNode } from '$lib/types';

  export let nodes: CategoryNode[] = [];
  export let currentId = 'root';
  export let depth = 0;

  const isAncestor = (id: string) => currentId === id || currentId.startsWith(`${id}/`);
  // open state per node id; ancestors of the current selection start open
  let open: Record<string, boolean> = {};
  $: for (const node of nodes) {
    if (!(node.id in open)) open[node.id] = isAncestor(node.id);
  }
  const toggle = (id: string) => (open = { ...open, [id]: !open[id] });
</script>

<ul class="tree" style={`--depth:${depth}`}>
  {#each nodes as node (node.id)}
    <li>
      <div class="row" class:selected={node.id === currentId}>
        {#if node.children.length}
          <button
            type="button"
            class="twist"
            class:open={open[node.id]}
            aria-label={open[node.id] ? 'Collapse' : 'Expand'}
            on:click={() => toggle(node.id)}
          >
            <ChevronRight size={15} />
          </button>
        {:else}
          <span class="twist spacer" />
        {/if}
        <a class="label" href={`/browse/${node.id}`} title={node.label}>{node.label}</a>
        <span class="count">{node.allPages.length.toLocaleString()}</span>
      </div>
      {#if node.children.length && open[node.id]}
        <svelte:self nodes={node.children} {currentId} depth={depth + 1} />
      {/if}
    </li>
  {/each}
</ul>

<style>
  .tree {
    display: grid;
    gap: 2px;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  :global(.tree .tree) {
    margin: 2px 0 2px 10px;
    padding-left: 8px;
    border-left: 1px solid var(--line);
  }
  .row {
    display: grid;
    grid-template-columns: 22px minmax(0, 1fr) auto;
    align-items: center;
    gap: 4px;
    border-radius: var(--radius-sm);
  }
  .row:hover {
    background: rgba(11, 112, 111, 0.07);
  }
  .row.selected {
    background: var(--brand-tint);
  }
  .twist {
    display: grid;
    place-items: center;
    width: 22px;
    height: 30px;
    border: 0;
    background: transparent;
    color: var(--ink-soft);
    cursor: pointer;
    padding: 0;
  }
  .twist.spacer {
    cursor: default;
  }
  .twist :global(svg) {
    transition: transform 0.12s ease;
  }
  .twist.open :global(svg) {
    transform: rotate(90deg);
  }
  .label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    padding: 6px 4px;
    color: #2c3135;
    text-decoration: none;
  }
  .row.selected .label {
    color: var(--brand-dark);
    font-weight: 800;
  }
  .label:hover {
    color: var(--brand-dark);
  }
  .count {
    min-width: 26px;
    padding: 2px 7px;
    border-radius: 999px;
    background: rgba(27, 42, 46, 0.07);
    color: var(--ink-soft);
    font-size: 12px;
    font-weight: 750;
    text-align: center;
  }
</style>
