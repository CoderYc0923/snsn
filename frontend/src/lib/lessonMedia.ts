import { get, writable } from 'svelte/store'
import type { Cue } from './demo'
import { cueIndex, loopEnabled, playbackRate, playing } from './nav'

export const mediaCurrentMs = writable(0)
export const mediaDurationMs = writable(0)
export const mediaReady = writable(false)

let media: HTMLMediaElement | null = null
let raf = 0
let boundLessonId: string | null = null
let segmentEndMs: number | null = null
let segmentRaf = 0
let echoAudio: HTMLAudioElement | null = null
let loopGapTimer: ReturnType<typeof setTimeout> | null = null
let loopGapActive = false

const LOOP_GAP_MS = 1500

function clearLoopGap() {
  if (loopGapTimer) {
    clearTimeout(loopGapTimer)
    loopGapTimer = null
  }
  loopGapActive = false
}

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
  stopSegmentWatch()
  stopEchoAudio()
  clearLoopGap()
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
  clearLoopGap()
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

export function pauseMedia() {
  stopSegmentWatch()
  stopEchoAudio()
  clearLoopGap()
  media?.pause()
}

export async function playMedia() {
  if (!media) return
  clearLoopGap()
  stopEchoAudio()
  media.playbackRate = get(playbackRate)
  await media.play().catch(() => undefined)
}

export async function togglePlay() {
  if (!media) return
  if (media.paused) {
    await playMedia()
  } else {
    pauseMedia()
  }
}

export function applyRate(rate: number) {
  if (media) media.playbackRate = rate
}

function stopSegmentWatch() {
  if (segmentRaf) cancelAnimationFrame(segmentRaf)
  segmentRaf = 0
  segmentEndMs = null
}

function watchSegmentEnd() {
  const tick = () => {
    if (!media || segmentEndMs == null) return
    if (media.paused) {
      stopSegmentWatch()
      return
    }
    if (media.currentTime * 1000 >= segmentEndMs - 40) {
      media.pause()
      seekMs(Math.max(0, (segmentEndMs ?? 0) - 20))
      stopSegmentWatch()
      return
    }
    segmentRaf = requestAnimationFrame(tick)
  }
  segmentRaf = requestAnimationFrame(tick)
}

/** Play only [startMs, endMs) then pause. Stops any echo recording audio. */
export async function playCueSegment(cue: Cue) {
  if (!media) return
  stopEchoAudio()
  stopSegmentWatch()
  seekMs(cue.startMs)
  segmentEndMs = cue.endMs
  media.playbackRate = get(playbackRate)
  await media.play().catch(() => undefined)
  watchSegmentEnd()
}

export function stopEchoAudio() {
  if (!echoAudio) return
  echoAudio.pause()
  const src = echoAudio.src
  echoAudio.removeAttribute('src')
  echoAudio.load()
  if (src.startsWith('blob:')) URL.revokeObjectURL(src)
  echoAudio = null
}

/** Pause lesson media and play a user recording blob. */
export async function playRecordingBlob(blob: Blob) {
  pauseMedia()
  stopEchoAudio()
  const url = URL.createObjectURL(blob)
  const audio = new Audio(url)
  echoAudio = audio
  audio.onended = () => {
    if (echoAudio === audio) stopEchoAudio()
  }
  audio.onerror = () => {
    if (echoAudio === audio) stopEchoAudio()
  }
  await audio.play().catch(() => {
    stopEchoAudio()
  })
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

/** Keep single-cue loop while playing; pause ~1.5s between repeats. */
export function enforceCueLoop(cue: Cue | null) {
  if (!media || !cue || !get(loopEnabled)) return
  if (segmentEndMs != null) return
  if (loopGapActive) return
  if (media.paused) return
  if (media.currentTime * 1000 < cue.endMs - 40) return

  loopGapActive = true
  media.pause()
  const startMs = cue.startMs
  loopGapTimer = setTimeout(() => {
    loopGapTimer = null
    loopGapActive = false
    if (!media || !get(loopEnabled)) return
    media.currentTime = startMs / 1000
    mediaCurrentMs.set(startMs)
    void media.play().catch(() => undefined)
  }, LOOP_GAP_MS)
}

export function syncCueIndex(cues: Cue[]) {
  if (!cues.length) return
  const t = get(mediaCurrentMs)
  const next = indexForTime(cues, t)
  if (next !== get(cueIndex)) cueIndex.set(next)
}
