<script lang="ts">
  import { goTab, route } from '../lib/nav'
  import Icon from './Icon.svelte'
  import type { IconName } from './Icon.svelte'

  const tabs: { id: 'home' | 'lessons' | 'settings'; label: string; icon: IconName }[] = [
    { id: 'home', label: '首页', icon: 'home' },
    { id: 'lessons', label: '课列表', icon: 'list' },
    { id: 'settings', label: '设置', icon: 'settings' },
  ]
</script>

<nav class="bottom-nav" aria-label="主导航">
  {#each tabs as tab}
    <button
      class="tab"
      class:active={$route === tab.id}
      type="button"
      onclick={() => goTab(tab.id)}
    >
      <span class="icon-wrap">
        <Icon name={tab.icon} size={22} />
      </span>
      <span class="label">{tab.label}</span>
    </button>
  {/each}
</nav>

<style>
  .bottom-nav {
    width: min(320px, calc(100% - 36px));
    margin: 0 auto 10px;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 4px;
    padding: 8px;
    border-radius: 28px;
    background: rgba(255, 255, 255, 0.96);
    box-shadow: var(--shadow-float);
    backdrop-filter: blur(10px);
  }

  .tab {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: 4px 0 2px;
    color: var(--ink);
    font-size: 0.72rem;
    font-weight: 650;
  }

  .icon-wrap {
    width: 48px;
    height: 36px;
    border-radius: 12px;
    display: grid;
    place-items: center;
  }

  .tab.active .icon-wrap {
    background: var(--accent);
  }

  .tab.active {
    color: var(--accent-ink);
  }
</style>
