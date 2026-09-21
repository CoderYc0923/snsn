<script lang="ts">
  import { onMount } from 'svelte'
  import { initStorage, route, storageReady } from './lib/nav'
  import { clearToast, toastMessage } from './lib/importJob'
  import HomePage from './routes/HomePage.svelte'
  import LessonPage from './routes/LessonPage.svelte'
  import SettingsPage from './routes/SettingsPage.svelte'
  import PodcastPage from './routes/PodcastPage.svelte'

  onMount(() => {
    void initStorage()
  })
</script>

<div class="phone-frame">
  {#if !$storageReady}
    <div class="boot">加载中…</div>
  {:else if $route === 'home'}
    <HomePage />
  {:else if $route === 'lesson'}
    <LessonPage />
  {:else if $route === 'podcast'}
    <PodcastPage />
  {:else}
    <SettingsPage />
  {/if}

  {#if $toastMessage}
    <div class="toast" role="status">
      <p>{$toastMessage}</p>
      <button type="button" aria-label="关闭提示" onclick={() => clearToast()}>×</button>
    </div>
  {/if}
</div>

<style>
  .boot {
    flex: 1;
    display: grid;
    place-items: center;
    color: var(--ink-soft);
    font-weight: 650;
  }

  .toast {
    position: absolute;
    left: 16px;
    right: 16px;
    bottom: calc(88px + var(--sab));
    z-index: 80;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 12px 12px 14px;
    border-radius: 16px;
    background: rgba(45, 62, 47, 0.92);
    color: #fff;
    box-shadow: 0 10px 28px rgba(45, 62, 47, 0.28);
  }

  .toast p {
    margin: 0;
    flex: 1;
    font-size: 0.88rem;
    font-weight: 650;
    line-height: 1.35;
  }

  .toast button {
    width: 28px;
    height: 28px;
    border-radius: 999px;
    color: #fff;
    font-size: 1.1rem;
    line-height: 1;
    background: rgba(255, 255, 255, 0.12);
  }
</style>
