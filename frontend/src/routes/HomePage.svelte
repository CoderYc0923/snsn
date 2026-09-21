<script lang="ts">
  import { lessons, openLesson } from '../lib/nav'
  import { importTasks, startImport } from '../lib/importJob'
  import type { Lesson } from '../lib/demo'
  import BottomNav from '../components/BottomNav.svelte'
  import ImportProgressCard from '../components/ImportProgressCard.svelte'
  import Icon from '../components/Icon.svelte'

  let fileInput: HTMLInputElement | undefined = $state()

  const importing = $derived($importTasks.some((t) => t.status === 'running'))
  const empty = $derived($lessons.length === 0 && $importTasks.length === 0)

  function formatDuration(ms: number) {
    const s = Math.round(ms / 1000)
    const m = Math.floor(s / 60)
    const r = s % 60
    return `${m}:${r.toString().padStart(2, '0')}`
  }

  function grouped(items: Lesson[]) {
    const map = new Map<string, Lesson[]>()
    for (const lesson of items) {
      const list = map.get(lesson.date) ?? []
      list.push(lesson)
      map.set(lesson.date, list)
    }
    return [...map.entries()]
  }

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
    {:else if $lessons.length}
      {#each grouped($lessons) as [date, items] (date)}
        <section class="group">
          <h2>{date}</h2>
          {#each items as lesson (lesson.id)}
            {#if lesson.kind === 'audio'}
              <button class="guide-card" type="button" onclick={() => openLesson(lesson.id)}>
                <div class="guide-copy">
                  <div class="mic-row">
                    <span class="mic">
                      <Icon name="mic" size={14} />
                    </span>
                    <span class="dur">{formatDuration(lesson.durationMs)}</span>
                  </div>
                  <p>{lesson.title}</p>
                </div>
                <div class="bean" aria-hidden="true">
                  <Icon name="people" size={28} />
                </div>
              </button>
            {:else}
              <button class="video-card" type="button" onclick={() => openLesson(lesson.id)}>
                <div class="thumb">
                  <span class="play">
                    <Icon name="play" size={28} stroke={1.6} />
                  </span>
                  <span class="dur">{formatDuration(lesson.durationMs)}</span>
                  <span class="label">{lesson.posterLabel}</span>
                </div>
                <div class="meta">
                  <p>{lesson.title}</p>
                </div>
              </button>
            {/if}
          {/each}
        </section>
      {/each}
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

  .video-card,
  .guide-card {
    width: 100%;
    text-align: left;
    border-radius: var(--radius-lg);
    overflow: hidden;
    margin-bottom: 12px;
    box-shadow: var(--shadow-card);
  }

  .video-card {
    background: var(--bg-card);
  }

  .thumb {
    position: relative;
    aspect-ratio: 16 / 10;
    background:
      linear-gradient(160deg, rgba(111, 143, 78, 0.18), transparent 45%),
      linear-gradient(135deg, #c8d7b8 0%, #e7d7b4 48%, #d5e6c4 100%);
  }

  .play {
    position: absolute;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    width: 44px;
    height: 44px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.88);
    color: var(--accent-ink);
    display: grid;
    place-items: center;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  }

  .dur {
    position: absolute;
    left: 12px;
    bottom: 10px;
    font-size: 0.75rem;
    font-weight: 700;
    color: #fff;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
  }

  .thumb .label {
    position: absolute;
    right: 12px;
    top: 12px;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 4px 8px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.82);
    color: var(--accent-ink);
  }

  .meta {
    padding: 12px 14px 14px;
  }

  .meta p,
  .guide-copy p {
    margin: 0;
    font-size: 0.98rem;
    font-weight: 700;
    line-height: 1.4;
  }

  .guide-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 16px 16px 16px 18px;
    background: linear-gradient(120deg, #d8f0b0 0%, #e8f5c8 40%, #f3d7b0 100%);
    min-height: 96px;
  }

  .mic-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    color: var(--accent-ink);
  }

  .guide-card .dur {
    position: static;
    color: var(--ink-soft);
    text-shadow: none;
  }

  .mic {
    width: 24px;
    height: 24px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.7);
    display: grid;
    place-items: center;
  }

  .bean {
    width: 64px;
    height: 64px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.55);
    display: grid;
    place-items: center;
    color: var(--accent-deep);
    flex-shrink: 0;
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
