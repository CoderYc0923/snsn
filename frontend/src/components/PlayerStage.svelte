<script lang="ts">
  import { onDestroy } from 'svelte'
  import { getMediaCache } from '../lib/storage'
  import { bindMedia, unbindMedia } from '../lib/lessonMedia'

  let {
    lessonId,
    kind,
    posterLabel,
    overlayText = '',
    durationHintMs = 0,
  }: {
    lessonId: string
    kind: 'video' | 'audio'
    posterLabel: string
    overlayText?: string
    durationHintMs?: number
  } = $props()

  let src = $state<string | null>(null)
  let missing = $state(false)
  let mediaEl: HTMLMediaElement | undefined = $state()

  $effect(() => {
    const id = lessonId
    let objectUrl: string | null = null
    let cancelled = false
    src = null
    missing = false
    unbindMedia()

    void (async () => {
      const record = await getMediaCache(id)
      if (cancelled) return
      if (!record) {
        missing = true
        return
      }
      objectUrl = URL.createObjectURL(record.blob)
      src = objectUrl
    })()

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  })

  $effect(() => {
    if (mediaEl && src) {
      bindMedia(mediaEl, lessonId, durationHintMs)
    }
  })

  onDestroy(() => {
    unbindMedia()
  })
</script>

<section class="player" aria-label="播放器">
  <div class="frame">
    {#if src && kind === 'video'}
      <video
        class="media"
        bind:this={mediaEl}
        playsinline
        preload="metadata"
        src={src}
      >
        <track kind="captions" />
      </video>
    {:else if src}
      <div class="audio-shell">
        <p class="sub top">{overlayText || posterLabel}</p>
        <audio class="hidden-audio" bind:this={mediaEl} preload="metadata" src={src}></audio>
      </div>
    {:else}
      <div class="poster">
        <p class="sub top">{overlayText || posterLabel}</p>
        <p class="hint">{missing ? '未缓存原片，请重新导入本地文件' : '加载媒体…'}</p>
      </div>
    {/if}
  </div>
</section>

<style>
  .player {
    padding: 0 14px;
  }

  .frame {
    border-radius: var(--radius-lg);
    overflow: hidden;
    background: #111;
    box-shadow: var(--shadow-card);
  }

  .media {
    display: block;
    width: 100%;
    max-height: 42vh;
    background: #000;
  }

  .hidden-audio {
    position: absolute;
    width: 0;
    height: 0;
    opacity: 0;
    pointer-events: none;
  }

  .audio-shell,
  .poster {
    aspect-ratio: 16 / 10;
    background:
      linear-gradient(180deg, rgba(0, 0, 0, 0.15), transparent 35%),
      linear-gradient(145deg, #8fa87a 0%, #cbb892 45%, #9bb48a 100%);
    position: relative;
    display: grid;
    place-items: center;
  }

  .sub {
    margin: 0;
    position: absolute;
    left: 12px;
    right: 12px;
    text-align: center;
    color: #fff;
    font-family: var(--font-jp);
    font-weight: 700;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.55);
  }

  .sub.top {
    top: 14px;
    font-size: 0.95rem;
  }

  .hint {
    margin: 0;
    color: rgba(255, 255, 255, 0.78);
    font-size: 0.82rem;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
  }
</style>
