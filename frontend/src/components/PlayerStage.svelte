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

{#if kind === 'video'}
  <section class="player" aria-label="播放器">
    <div class="frame">
      {#if src}
        <div class="video-box">
          <video class="media" bind:this={mediaEl} playsinline preload="metadata" src={src}>
            <track kind="captions" />
          </video>
          {#if overlayText}
            <p class="caption">{overlayText}</p>
          {/if}
        </div>
      {:else}
        <div class="poster">
          <p class="sub top">{overlayText || posterLabel}</p>
          <p class="hint">{missing ? '未缓存原片，请重新导入本地文件' : '加载媒体…'}</p>
        </div>
      {/if}
    </div>
  </section>
{:else if src}
  <audio class="sr-only-media" bind:this={mediaEl} preload="metadata" src={src}></audio>
{:else if missing}
  <p class="audio-missing muted">未缓存原片，请重新导入本地文件</p>
{/if}

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

  .video-box {
    position: relative;
  }

  .media {
    display: block;
    width: 100%;
    max-height: 42vh;
    background: #000;
  }

  .caption {
    position: absolute;
    left: 10px;
    right: 10px;
    bottom: 12px;
    margin: 0;
    padding: 8px 10px;
    border-radius: 10px;
    background: rgba(0, 0, 0, 0.55);
    color: #fff;
    font-family: var(--font-jp);
    font-size: 0.92rem;
    font-weight: 700;
    line-height: 1.45;
    text-align: center;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45);
    pointer-events: none;
  }

  .sr-only-media {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

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

  .audio-missing {
    margin: 8px 18px 0;
    font-size: 0.85rem;
    font-weight: 650;
  }
</style>
