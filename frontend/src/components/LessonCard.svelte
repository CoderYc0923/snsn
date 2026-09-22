<script lang="ts">
  import type { Lesson } from '../lib/demo'
  import Icon from './Icon.svelte'

  let {
    lesson,
    onclick,
  }: {
    lesson: Lesson
    onclick: () => void
  } = $props()

  function formatDuration(ms: number) {
    const s = Math.round(ms / 1000)
    const m = Math.floor(s / 60)
    const r = s % 60
    return `${m}:${r.toString().padStart(2, '0')}`
  }
</script>

{#if lesson.kind === 'audio'}
  <button class="guide-card" type="button" {onclick}>
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
  <button class="video-card" type="button" {onclick}>
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

<style>
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
</style>
