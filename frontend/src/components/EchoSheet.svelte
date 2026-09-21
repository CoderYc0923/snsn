<script lang="ts">
  import type { Cue } from '../lib/demo'
  import { echoSheetOpen, shadowStep } from '../lib/nav'
  import type { ShadowStep } from '../lib/demo'
  import CueCard from './CueCard.svelte'
  import Icon from './Icon.svelte'

  let { cue }: { cue: Cue } = $props()

  const steps: { id: ShadowStep; label: string }[] = [
    { id: 'listen', label: '听' },
    { id: 'echo', label: '回声' },
    { id: 'speak', label: '说' },
    { id: 'playback', label: '回放' },
  ]

  function close() {
    echoSheetOpen.set(false)
  }
</script>

<div
  class="overlay"
  role="button"
  tabindex="0"
  aria-label="关闭跟读面板"
  onclick={close}
  onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && close()}
>
  <div
    class="sheet"
    role="dialog"
    tabindex="-1"
    aria-label="影子跟读"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.key === 'Escape' && close()}
  >
    <div class="handle" aria-hidden="true"></div>

    <div class="body">
      <CueCard {cue} active />

      <div class="modes" role="tablist" aria-label="跟读模式">
        {#each steps as step}
          <button
            class="mode"
            class:active={$shadowStep === step.id}
            type="button"
            role="tab"
            aria-selected={$shadowStep === step.id}
            onclick={() => shadowStep.set(step.id)}
          >
            {step.label}
          </button>
        {/each}
      </div>

      <button class="listen-link" type="button">听音频</button>
    </div>

    <div class="footer">
      <button class="side" type="button">
        <span class="circle">
          <Icon name="auto-echo" size={18} />
        </span>
        自动回声
      </button>
      <button class="side" type="button">
        <span class="circle">
          <Icon name="explain" size={18} />
        </span>
        解释
      </button>
      <button class="mic" type="button" aria-label="跟读录音">
        <Icon name="mic" size={26} />
      </button>
    </div>
  </div>
</div>

<style>
  .overlay {
    position: absolute;
    inset: 0;
    background: rgba(45, 62, 47, 0.22);
    display: flex;
    align-items: flex-end;
    z-index: 50;
  }

  .sheet {
    width: 100%;
    background: #fff;
    border-radius: 28px 28px 0 0;
    padding: 8px 14px max(14px, var(--sab));
    box-shadow: 0 -10px 40px rgba(45, 62, 47, 0.12);
    animation: rise 0.22s ease;
  }

  @keyframes rise {
    from {
      transform: translateY(28px);
    }
    to {
      transform: translateY(0);
    }
  }

  .handle {
    width: 40px;
    height: 4px;
    border-radius: 999px;
    background: #d7dece;
    margin: 4px auto 12px;
  }

  .body {
    border-radius: var(--radius-lg);
    background: var(--bg-sage);
    padding: 12px;
  }

  .modes {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    margin-top: 12px;
  }

  .mode {
    min-height: 42px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.72);
    color: var(--ink-soft);
    font-weight: 750;
    font-size: 0.9rem;
    position: relative;
    overflow: hidden;
  }

  .mode.active {
    background: #fff;
    color: var(--accent-ink);
    box-shadow: 0 1px 4px rgba(45, 62, 47, 0.06);
  }

  .mode.active::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 5px;
    background: var(--accent);
  }

  .listen-link {
    display: block;
    width: 100%;
    margin-top: 10px;
    text-align: center;
    color: var(--accent-deep);
    font-size: 0.85rem;
    font-weight: 700;
  }

  .footer {
    display: grid;
    grid-template-columns: 1fr 1fr auto;
    gap: 8px;
    align-items: center;
    margin-top: 14px;
    padding: 0 4px;
  }

  .side {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    font-size: 0.75rem;
    font-weight: 650;
    color: var(--ink-soft);
  }

  .circle {
    width: 40px;
    height: 40px;
    border-radius: 999px;
    background: var(--bg-sage);
    display: grid;
    place-items: center;
    color: var(--accent-ink);
  }

  .mic {
    width: 64px;
    height: 64px;
    border-radius: 999px;
    background: #fff;
    color: var(--accent-ink);
    display: grid;
    place-items: center;
    box-shadow: var(--shadow-float);
  }
</style>
