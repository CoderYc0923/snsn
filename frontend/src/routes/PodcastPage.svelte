<script lang="ts">
  import BottomNav from '../components/BottomNav.svelte'
</script>

<main class="page podcast">
  <header class="page-pad head">
    <h1>播客</h1>
    <p class="muted">样式占位 · 稍后接入播客源</p>
  </header>

  <div class="page-body page-pad">
    <div class="empty">
      <p>还没有播客内容</p>
    </div>
  </div>

  <div class="page-footer">
    <BottomNav />
  </div>
</main>

<style>
  .head {
    flex-shrink: 0;
  }

  .head h1 {
    margin: 12px 0 6px;
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: -0.04em;
  }

  .head p {
    margin: 0 0 12px;
  }

  .empty {
    border-radius: var(--radius-lg);
    background: var(--bg-sage);
    padding: 48px 16px;
    text-align: center;
    color: var(--ink-soft);
    font-weight: 650;
  }
</style>
