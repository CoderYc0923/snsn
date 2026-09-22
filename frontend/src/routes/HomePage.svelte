<script lang="ts">
  import { lessons, openLesson, recentLesson } from '../lib/nav'
  import { importTasks, startImport } from '../lib/importJob'
  import BottomNav from '../components/BottomNav.svelte'
  import ImportProgressCard from '../components/ImportProgressCard.svelte'
  import LessonCard from '../components/LessonCard.svelte'
  import Icon from '../components/Icon.svelte'

  let fileInput: HTMLInputElement | undefined = $state()

  const importing = $derived($importTasks.some((t) => t.status === 'running'))
  const empty = $derived(!$recentLesson && $importTasks.length === 0)

  function pickFile() {
    if (importing) return
    fileInput?.click()
  }

  function onFileChange(event: Event) {
    const input = event.currentTarget as HTMLInputElement
    const file = input.files?.[0]
    input.value = ''
    if (!file) return
    void startImport(file)
  }
</script>

<main class="page home">
  <header class="brand-banner">
    <button
      class="add"
      type="button"
      aria-label="导入"
      disabled={importing}
      onclick={pickFile}
    >
      <Icon name="plus" size={22} stroke={2} />
    </button>
    <input
      class="sr-only"
      type="file"
      accept="video/*,audio/*"
      bind:this={fileInput}
      onchange={onFileChange}
    />

    <div class="brand-card" role="img" aria-label="SnSn">
      <div class="mascot">
        <svg class="cat" viewBox="0 0 120 100" aria-hidden="true">
          <ellipse cx="52" cy="78" rx="28" ry="16" fill="#1c1f1a" />
          <circle cx="52" cy="48" r="30" fill="#1c1f1a" />
          <path d="M28 36 L34 12 L48 30 Z" fill="#1c1f1a" />
          <path d="M76 36 L70 12 L56 30 Z" fill="#1c1f1a" />
          <ellipse cx="42" cy="48" rx="4.2" ry="5.5" fill="#eef6dc" />
          <ellipse cx="62" cy="48" rx="4.2" ry="5.5" fill="#eef6dc" />
          <path
            d="M78 82 C92 78, 104 62, 108 48 C110 42, 104 44, 100 50 C94 60, 86 72, 78 78"
            fill="none"
            stroke="#1c1f1a"
            stroke-width="7"
            stroke-linecap="round"
          />
        </svg>
      </div>
    </div>
  </header>

  <div class="page-body page-pad feed">
    {#if $importTasks.length}
      <section class="group">
        <h2>导入中</h2>
        {#each $importTasks as task (task.localId)}
          <ImportProgressCard {task} />
        {/each}
      </section>
    {/if}

    {#if empty}
      <section class="empty">
        <p class="empty-title">还没有课程</p>
        <p class="muted">点右上角 +，选择日语音视频即可后台转写。</p>
        <button class="empty-cta" type="button" disabled={importing} onclick={pickFile}
          >导入材料</button
        >
      </section>
    {:else if $recentLesson}
      <section class="group">
        <h2>最近使用</h2>
        <LessonCard lesson={$recentLesson} onclick={() => openLesson($recentLesson!.id)} />
        {#if $lessons.length > 1}
          <p class="more muted">全部课程请到「课列表」查看</p>
        {/if}
      </section>
    {/if}
  </div>

  <div class="page-footer">
    <BottomNav />
  </div>
</main>

<style>
  .home {
    background: var(--bg);
  }

  .brand-banner {
    position: relative;
    flex: 0 0 33%;
    min-height: 200px;
    max-height: 320px;
    padding: 14px max(16px, var(--sar)) 8px max(16px, var(--sal));
    display: flex;
    align-items: stretch;
  }

  .brand-card {
    flex: 1;
    border-radius: 28px;
    background:
      radial-gradient(120% 90% at 50% 0%, rgba(184, 232, 106, 0.35), transparent 55%),
      linear-gradient(180deg, #eef6dc 0%, #e3edd4 48%, #d8e6c8 100%);
    box-shadow: var(--shadow-card);
    display: grid;
    place-items: center;
    overflow: hidden;
    animation: brand-rise 0.55s ease-out both;
  }

  .mascot {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .cat {
    width: min(44vw, 176px);
    height: auto;
    display: block;
    animation: cat-bob 3.6s ease-in-out infinite;
  }

  .add {
    position: absolute;
    top: 22px;
    right: max(26px, calc(var(--sar) + 22px));
    z-index: 3;
    width: 42px;
    height: 42px;
    border-radius: 14px;
    background: rgba(255, 255, 255, 0.72);
    color: var(--accent-ink);
    display: grid;
    place-items: center;
    box-shadow: 0 4px 14px rgba(45, 62, 47, 0.1);
    backdrop-filter: blur(6px);
  }

  .add:disabled {
    opacity: 0.5;
  }

  .feed {
    display: flex;
    flex-direction: column;
    gap: 18px;
    padding-top: 12px;
    padding-bottom: 12px;
  }

  .empty {
    margin-top: 28px;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
  }

  .empty-title {
    margin: 0;
    font-size: 1.15rem;
    font-weight: 800;
  }

  .empty .muted {
    margin: 0;
    max-width: 16rem;
    line-height: 1.5;
  }

  .empty-cta {
    margin-top: 8px;
    min-height: 44px;
    padding: 0 22px;
    border-radius: 999px;
    background: var(--accent);
    color: var(--accent-ink);
    font-weight: 800;
  }

  .empty-cta:disabled {
    opacity: 0.55;
  }

  .group h2 {
    margin: 0 0 10px;
    font-size: 0.92rem;
    font-weight: 700;
    color: var(--ink-soft);
  }

  .more {
    margin: 0;
    font-size: 0.82rem;
    font-weight: 600;
    text-align: center;
  }

  @keyframes brand-rise {
    from {
      opacity: 0;
      transform: translateY(10px) scale(0.98);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }

  @keyframes cat-bob {
    0%,
    100% {
      transform: translateY(0);
    }
    50% {
      transform: translateY(-4px);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .brand-card,
    .cat {
      animation: none;
    }
  }
</style>
