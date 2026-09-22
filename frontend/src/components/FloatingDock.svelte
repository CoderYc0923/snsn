<script lang="ts">
  import { cuePinned, echoSheetOpen, loopEnabled, playbackRate, playing } from '../lib/nav'
  import { applyRate, pauseMedia, togglePlay } from '../lib/lessonMedia'
  import Icon from './Icon.svelte'

  let {
    currentLabel,
    totalLabel,
    progress = 0,
  }: {
    currentLabel: string
    totalLabel: string
    progress?: number
  } = $props()

  const shown = $derived(Math.max(0, Math.min(1, progress)))

  function cycleRate() {
    const rates = [0.75, 1, 1.25, 1.5]
    const i = rates.indexOf($playbackRate)
    const next = rates[(i + 1) % rates.length] ?? 1
    playbackRate.set(next)
    applyRate(next)
  }

  function openExplain() {
    pauseMedia()
    echoSheetOpen.set(true)
  }
</script>

<div class="dock">
  <div class="scrub">
    <span>{currentLabel}</span>
    <div
      class="track"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(shown * 100)}
      aria-label="播放进度"
    >
      <i style="width: {Math.round(shown * 100)}%"></i>
      <b style="left: {Math.round(shown * 100)}%"></b>
    </div>
    <span>{totalLabel}</span>
  </div>

  <div class="row">
    <div class="actions">
      <button
        class="act"
        class:on={$cuePinned}
        type="button"
        title="固定当前句，播放时不高亮跳转"
        onclick={() => cuePinned.update((v) => !v)}
      >
        <Icon name="pin" size={20} />
        固定
      </button>
      <button class="act" type="button" onclick={openExplain}>
        <Icon name="explain" size={20} />
        解释
      </button>
      <button
        class="act"
        class:on={$loopEnabled}
        type="button"
        onclick={() => loopEnabled.update((v) => !v)}
      >
        <Icon name="repeat" size={20} />
        重复
      </button>
      <button class="act" type="button" onclick={cycleRate}>
        <Icon name="speed" size={20} />
        {$playbackRate}x
      </button>
      <button class="act" type="button" onclick={() => void togglePlay()}>
        <Icon name={$playing ? 'pause' : 'play'} size={20} />
        {$playing ? '暂停' : '播放'}
      </button>
    </div>
    <button class="primary" type="button" aria-label="影子跟读" onclick={openExplain}>
      <Icon name="people" size={22} />
    </button>
  </div>
</div>

<style>
  .dock {
    margin: 0 14px 10px;
    padding: 12px 14px 14px;
    border-radius: var(--radius-xl);
    background: rgba(238, 243, 232, 0.96);
    box-shadow: var(--shadow-dock);
    backdrop-filter: blur(8px);
  }

  .scrub {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 8px;
    align-items: center;
    margin-bottom: 10px;
    font-size: 0.72rem;
    color: var(--ink-faint);
    font-weight: 600;
  }

  .track {
    position: relative;
    height: 18px;
    display: flex;
    align-items: center;
    pointer-events: none;
  }

  .track::before {
    content: '';
    position: absolute;
    left: 0;
    right: 0;
    height: 4px;
    border-radius: 999px;
    background: rgba(111, 143, 78, 0.25);
  }

  .track i {
    position: absolute;
    left: 0;
    height: 4px;
    border-radius: 999px;
    background: var(--accent-deep);
  }

  .track b {
    position: absolute;
    top: 50%;
    width: 14px;
    height: 14px;
    border-radius: 999px;
    background: var(--accent-deep);
    transform: translate(-50%, -50%);
    box-shadow: 0 1px 4px rgba(45, 62, 47, 0.25);
  }

  .row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .actions {
    flex: 1;
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 2px;
  }

  .act {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 5px;
    font-size: 0.68rem;
    font-weight: 650;
    color: var(--ink-soft);
    padding: 4px 0;
  }

  .act.on {
    color: var(--accent-deep);
  }

  .primary {
    width: 52px;
    height: 52px;
    border-radius: 16px;
    background: var(--accent);
    color: var(--accent-ink);
    display: grid;
    place-items: center;
    flex-shrink: 0;
    box-shadow: 0 4px 14px rgba(184, 232, 106, 0.4);
  }
</style>
