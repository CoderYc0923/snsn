<script lang="ts">
  import type { Cue, WordTone } from '../lib/demo'

  let {
    cue,
    active = false,
  }: {
    cue: Cue
    active?: boolean
  } = $props()

  const toneClass: Record<WordTone, string> = {
    yellow: 't-yellow',
    blue: 't-blue',
    pink: 't-pink',
    orange: 't-orange',
    mint: 't-mint',
    none: 't-none',
  }

  const richWords = $derived(
    cue.words.some(
      (w) =>
        !!w.furigana ||
        !!w.romaji ||
        (w.tone && w.tone !== 'none') ||
        (w.text?.length ?? 0) > 1,
    ),
  )
</script>

<article class="cue-card" class:active={active}>
  {#if richWords}
    <div class="words">
      {#each cue.words as word, i (i)}
        <span class="word {toneClass[word.tone ?? 'none']}">
          {#if word.furigana}
            <span class="furi">{word.furigana}</span>
          {:else}
            <span class="furi spacer">&nbsp;</span>
          {/if}
          <span class="jp">{word.text}</span>
          {#if word.romaji}
            <span class="romaji">{word.romaji}</span>
          {:else}
            <span class="romaji spacer">&nbsp;</span>
          {/if}
        </span>
      {/each}
    </div>
  {:else}
    <p class="jp-plain">{cue.text}</p>
  {/if}
  {#if cue.translation}
    <p class="zh">{cue.translation}</p>
  {/if}
</article>

<style>
  .cue-card {
    padding: 16px 14px 14px;
    border-radius: var(--radius-lg);
    background: #f3f6ef;
    border: 1.5px solid transparent;
    transition:
      background 0.15s ease,
      border-color 0.15s ease,
      box-shadow 0.15s ease;
  }

  .cue-card.active {
    background: var(--accent-soft);
    border-color: rgba(184, 232, 106, 0.95);
    box-shadow: 0 0 0 2px rgba(184, 232, 106, 0.35);
  }

  .words {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 6px;
    align-items: flex-end;
    margin-bottom: 12px;
  }

  .word {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    min-width: 1.2em;
    padding: 0 2px 3px;
    border-radius: 6px;
  }

  .furi,
  .romaji {
    font-size: 0.58rem;
    line-height: 1.1;
    color: var(--ink-faint);
    font-weight: 500;
  }

  .jp {
    font-family: var(--font-jp);
    font-size: 1.2rem;
    font-weight: 700;
    line-height: 1.35;
    color: var(--ink);
  }

  .jp-plain {
    margin: 0 0 12px;
    font-family: var(--font-jp);
    font-size: 1.18rem;
    font-weight: 700;
    line-height: 1.55;
    color: var(--ink);
  }

  .t-yellow {
    box-shadow: inset 0 -6px 0 var(--hl-yellow);
  }
  .t-blue {
    box-shadow: inset 0 -6px 0 var(--hl-blue);
  }
  .t-pink {
    box-shadow: inset 0 -6px 0 var(--hl-pink);
  }
  .t-orange {
    box-shadow: inset 0 -6px 0 var(--hl-orange);
  }
  .t-mint {
    box-shadow: inset 0 -6px 0 var(--hl-mint);
  }

  .zh {
    margin: 0;
    font-size: 0.95rem;
    color: var(--ink-soft);
    font-weight: 500;
  }

  .spacer {
    visibility: hidden;
  }
</style>
