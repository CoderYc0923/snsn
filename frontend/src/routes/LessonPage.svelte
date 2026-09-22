<script lang="ts">
  import { derived } from 'svelte/store'
  import {
    activeLessonId,
    cueIndex,
    cuePinned,
    echoSheetOpen,
    goHome,
    lessons,
    loopEnabled,
    playbackRate,
  } from '../lib/nav'
  import {
    enforceCueLoop,
    mediaCurrentMs,
    mediaDurationMs,
    pauseMedia,
    seekMs,
    syncCueIndex,
    applyRate,
  } from '../lib/lessonMedia'
  import PlayerStage from '../components/PlayerStage.svelte'
  import CueCard from '../components/CueCard.svelte'
  import FloatingDock from '../components/FloatingDock.svelte'
  import EchoSheet from '../components/EchoSheet.svelte'
  import Icon from '../components/Icon.svelte'

  const lesson = derived([lessons, activeLessonId], ([$lessons, $id]) =>
    $lessons.find((item) => item.id === $id),
  )

  const cue = derived([lesson, cueIndex], ([$lesson, $index]) => {
    if (!$lesson) return null
    return $lesson.cues[$index] ?? null
  })

  let listEl: HTMLElement | undefined = $state()

  function formatMs(ms: number) {
    const total = Math.max(0, Math.floor(ms / 1000))
    const m = Math.floor(total / 60)
    const r = total % 60
    return `${m}:${r.toString().padStart(2, '0')}`
  }

  function selectCue(index: number) {
    const item = $lesson?.cues[index]
    if (!item) return
    cueIndex.set(index)
    seekMs(item.startMs)
  }

  $effect(() => {
    const cues = $lesson?.cues
    if (!cues?.length) return
    void $mediaCurrentMs
    if ($loopEnabled) enforceCueLoop($cue)
    else if (!$cuePinned) syncCueIndex(cues)
  })

  $effect(() => {
    applyRate($playbackRate)
  })

  $effect(() => {
    const idx = $cueIndex
    const root = listEl
    if (!root) return
    const node = root.querySelector(`[data-cue-index="${idx}"]`) as HTMLElement | null
    node?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  })

  const progress = $derived(
    $mediaDurationMs > 0 ? $mediaCurrentMs / $mediaDurationMs : 0,
  )
</script>

{#if $lesson && $cue}
  <main class="page lesson">
    <header class="bar page-pad">
      <button class="icon-btn" type="button" aria-label="返回" onclick={() => goHome()}>
        <Icon name="back" size={22} />
      </button>
      <h1>{$lesson.title}</h1>
      <button
        class="icon-btn"
        type="button"
        aria-label="字幕设置"
        onclick={() => {
          pauseMedia()
          echoSheetOpen.set(true)
        }}
      >
        <Icon name="captions" size={20} />
      </button>
    </header>

    <div class="player-wrap">
      <PlayerStage
        lessonId={$lesson.id}
        kind={$lesson.kind}
        posterLabel={$lesson.posterLabel}
        overlayText={$cue.text}
        durationHintMs={$lesson.durationMs}
      />
    </div>

    <div class="page-body page-pad cues" bind:this={listEl}>
      {#each $lesson.cues as item, index (item.id)}
        <button
          class="cue-hit"
          type="button"
          data-cue-index={index}
          onclick={() => selectCue(index)}
        >
          <CueCard cue={item} active={index === $cueIndex} />
        </button>
      {/each}
    </div>

    <div class="page-footer dock-wrap">
      <FloatingDock
        currentLabel={formatMs($mediaCurrentMs)}
        totalLabel={formatMs($mediaDurationMs || $lesson.durationMs)}
        progress={progress}
      />
    </div>

    {#if $echoSheetOpen}
      <EchoSheet lessonId={$lesson.id} cue={$cue} />
    {/if}
  </main>
{:else}
  <main class="page page-pad">
    <p class="muted">未找到课程</p>
    <button type="button" onclick={() => goHome()}>返回</button>
  </main>
{/if}

<style>
  .bar {
    flex-shrink: 0;
    display: grid;
    grid-template-columns: var(--tap) 1fr var(--tap);
    align-items: center;
    min-height: 48px;
    gap: 4px;
  }

  .bar h1 {
    margin: 0;
    text-align: center;
    font-size: 0.95rem;
    font-weight: 700;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .icon-btn {
    color: var(--ink);
  }

  .player-wrap {
    flex-shrink: 0;
  }

  .cues {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding-top: 14px;
    padding-bottom: 16px;
  }

  .cue-hit {
    width: 100%;
    text-align: left;
    padding: 0;
    border-radius: var(--radius-lg);
  }

  .dock-wrap {
    flex-shrink: 0;
  }
</style>
