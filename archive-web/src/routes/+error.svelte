<script lang="ts">
  import { page } from '$app/stores';
</script>

<div class="container state-screen">
  <h1>{$page.status}</h1>
  <p>{$page.error?.message ?? 'Something went wrong.'}</p>
  <p><a class="text-link" href="/">Back to home</a></p>
</div>
