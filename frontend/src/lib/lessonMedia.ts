import { get, writable } from 'svelte/store'
import type { Cue } from './demo'
import { cueIndex, loopEnabled, playbackRate, playing } from './nav'

export const mediaCurrentMs = writable(0)
export const mediaDurationMs = writable(0)
export const mediaReady = writable(false)

let media: HTMLMediaElement | null = null
let raf = 0
let boundLessonId: string | null = null

export function bindMedia(el: HTMLMediaElement | null, lessonId: string, durationHintMs = 0) {
  unbindMedia()
  media = el
  boundLessonId = lessonId
  mediaReady.set(!!el)
  mediaCurrentMs.set(0)
  mediaDurationMs.set(durationHintMs)

  if (!el) return

  const onMeta = () => {
    const d = el.duration
    if (Number.isFinite(d) && d > 0) mediaDurationMs.set(d * 1000)
  }
  const onTime = () => mediaCurrentMs.set(el.currentTime * 1000)
  const onPlay = () => playing.set(true)
  const onPause = () => playing.set(false)
  const onEnded = () => {
    playing.set(false)
    if (get(loopEnabled)) {
      // loop handled by cue watcher in LessonPage
    }
  }

  el.addEventListener('loadedmetadata', onMeta)
  el.addEventListener('durationchange', onMeta)
  el.addEventListener('timeupdate', onTime)
  el.addEventListener('play', onPlay)
  el.addEventListener('pause', onPause)
  el.addEventListener('ended', onEnded)
  onMeta()

  ;(el as HTMLMediaElement & { __snsnCleanup?: () => void }).__snsnCleanup = () => {
    el.removeEventListener('loadedmetadata', onMeta)
    el.removeEventListener('durationchange', onMeta)
    el.removeEventListener('timeupdate', onTime)
    el.removeEventListener('play', onPlay)
    el.removeEventListener('pause', onPause)
    el.removeEventListener('ended', onEnded)
  }
}

export function unbindMedia() {
  if (raf) cancelAnimationFrame(raf)
  raf = 0
  if (media) {
    const cleanup = (media as HTMLMediaElement & { __snsnCleanup?: () => void }).__snsnCleanup
    cleanup?.()
    media.pause()
  }
  media = null
  boundLessonId = null
  mediaReady.set(false)
  playing.set(false)
}

export function getBoundLessonId() {
  return boundLessonId
}

export function seekMs(ms: number) {
  if (!media) return
  const dur = media.duration
  const sec = Math.max(0, ms / 1000)
  media.currentTime = Number.isFinite(dur) ? Math.min(sec, Math.max(0, dur - 0.05)) : sec
  mediaCurrentMs.set(media.currentTime * 1000)
}

export function seekRatio(ratio: number) {
  const dur = get(mediaDurationMs)
  seekMs(Math.max(0, Math.min(1, ratio)) * dur)
}

export async function togglePlay() {
  if (!media) return
  if (media.paused) {
    media.playbackRate = get(playbackRate)
    await media.play().catch(() => undefined)
  } else {
    media.pause()
  }
}

export function applyRate(rate: number) {
  if (media) media.playbackRate = rate
}

export function indexForTime(cues: Cue[], timeMs: number): number {
  if (!cues.length) return 0
  let idx = 0
  for (let i = 0; i < cues.length; i++) {
    if (timeMs >= cues[i].startMs) idx = i
    if (timeMs < cues[i].endMs) return i
  }
  return idx
}

/** Keep single-cue loop while playing. */
export function enforceCueLoop(cue: Cue | null) {
  if (!media || !cue || !get(loopEnabled) || media.paused) return
  if (media.currentTime * 1000 >= cue.endMs - 40) {
    media.currentTime = cue.startMs / 1000
  }
}

export function syncCueIndex(cues: Cue[]) {
  if (!cues.length) return
  const t = get(mediaCurrentMs)
  const next = indexForTime(cues, t)
  if (next !== get(cueIndex)) cueIndex.set(next)
}
