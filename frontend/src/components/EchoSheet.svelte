<script lang="ts">
  import { onDestroy, onMount } from 'svelte'
  import type { Cue } from '../lib/demo'
  import { echoSheetOpen, shadowStep } from '../lib/nav'
  import type { ShadowStep } from '../lib/demo'
  import {
    pauseMedia,
    playCueSegment,
    playRecordingBlob,
    stopEchoAudio,
  } from '../lib/lessonMedia'
  import {
    deleteCueRecording,
    listCueRecordings,
    putCueRecording,
    type CueRecording,
  } from '../lib/storage'
  import CueCard from './CueCard.svelte'
  import Icon from './Icon.svelte'

  let { lessonId, cue }: { lessonId: string; cue: Cue } = $props()

  const steps: { id: ShadowStep; label: string }[] = [
    { id: 'listen', label: '听' },
    { id: 'echo', label: '回声' },
    { id: 'speak', label: '说' },
    { id: 'playback', label: '回放' },
  ]

  type Panel = 'none' | 'echo-list' | 'record'
  let panel = $state<Panel>('none')
  let recordings = $state<CueRecording[]>([])
  let listBusy = $state(false)
  let listError = $state<string | null>(null)

  let recording = $state(false)
  let recordError = $state<string | null>(null)
  let mediaRecorder: MediaRecorder | null = null
  let mediaStream: MediaStream | null = null
  let recordedChunks: BlobPart[] = []
  let audioCtx: AudioContext | null = null
  let analyser: AnalyserNode | null = null
  let waveRaf = 0
  let waveBars = $state<number[]>(Array.from({ length: 24 }, () => 0.18))
  let pendingBlob = $state<Blob | null>(null)

  onMount(() => {
    pauseMedia()
  })

  onDestroy(() => {
    teardownRecorder()
    stopEchoAudio()
  })

  function close() {
    teardownRecorder()
    stopEchoAudio()
    pauseMedia()
    echoSheetOpen.set(false)
  }

  async function refreshRecordings() {
    listBusy = true
    listError = null
    try {
      recordings = await listCueRecordings(lessonId, cue.id)
    } catch (e) {
      listError = e instanceof Error ? e.message : '读取录音失败'
      recordings = []
    } finally {
      listBusy = false
    }
  }

  async function onStep(step: ShadowStep) {
    shadowStep.set(step)
    recordError = null
    listError = null

    if (step === 'listen') {
      panel = 'none'
      teardownRecorder()
      await playCueSegment(cue)
      return
    }

    if (step === 'playback') {
      panel = 'none'
      teardownRecorder()
      pauseMedia()
      stopEchoAudio()
      await playCueSegment(cue)
      return
    }

    if (step === 'echo') {
      teardownRecorder()
      pauseMedia()
      stopEchoAudio()
      panel = 'echo-list'
      await refreshRecordings()
      return
    }

    if (step === 'speak') {
      pauseMedia()
      stopEchoAudio()
      panel = 'record'
      await startRecording()
    }
  }

  async function playRecording(rec: CueRecording) {
    pauseMedia()
    await playRecordingBlob(rec.blob)
  }

  async function removeRecording(id: string) {
    if (!confirm('删除这条录音？')) return
    await deleteCueRecording(id)
    await refreshRecordings()
  }

  function teardownRecorder() {
    if (waveRaf) cancelAnimationFrame(waveRaf)
    waveRaf = 0
    if (mediaRecorder) {
      mediaRecorder.ondataavailable = null
      mediaRecorder.onstop = null
      try {
        if (mediaRecorder.state === 'recording') mediaRecorder.stop()
      } catch {
        /* ignore */
      }
    }
    mediaRecorder = null
    mediaStream?.getTracks().forEach((t) => t.stop())
    mediaStream = null
    audioCtx?.close().catch(() => undefined)
    audioCtx = null
    analyser = null
    recording = false
    recordedChunks = []
    pendingBlob = null
  }

  function tickWave() {
    if (!analyser) return
    const data = new Uint8Array(analyser.frequencyBinCount)
    analyser.getByteFrequencyData(data)
    const bars = waveBars.length
    const next: number[] = []
    const step = Math.max(1, Math.floor(data.length / bars))
    for (let i = 0; i < bars; i++) {
      let sum = 0
      for (let j = 0; j < step; j++) sum += data[i * step + j] ?? 0
      const avg = sum / step / 255
      next.push(0.12 + avg * 0.88)
    }
    waveBars = next
    waveRaf = requestAnimationFrame(tickWave)
  }

  async function startRecording() {
    teardownRecorder()
    recordError = null
    pendingBlob = null
    if (!navigator.mediaDevices?.getUserMedia) {
      recordError = '当前环境不支持录音'
      return
    }
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      recordError = '无法使用麦克风，请在浏览器中允许录音权限后重试'
      return
    }

    try {
      audioCtx = new AudioContext()
      const source = audioCtx.createMediaStreamSource(mediaStream)
      analyser = audioCtx.createAnalyser()
      analyser.fftSize = 128
      source.connect(analyser)
      tickWave()
    } catch {
      /* wave is optional */
    }

    const mime =
      MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : ''
    recordedChunks = []
    mediaRecorder = mime ? new MediaRecorder(mediaStream, { mimeType: mime }) : new MediaRecorder(mediaStream)
    mediaRecorder.ondataavailable = (ev) => {
      if (ev.data.size > 0) recordedChunks.push(ev.data)
    }
    mediaRecorder.onstop = () => {
      const type = mediaRecorder?.mimeType || mime || 'audio/webm'
      const blob = new Blob(recordedChunks, { type })
      recordedChunks = []
      recording = false
      mediaStream?.getTracks().forEach((t) => t.stop())
      mediaStream = null
      if (waveRaf) cancelAnimationFrame(waveRaf)
      waveRaf = 0
      pendingBlob = blob
      void afterStopRecording(blob)
    }
    mediaRecorder.start(200)
    recording = true
  }

  async function afterStopRecording(blob: Blob) {
    if (blob.size < 200) {
      recordError = '录音太短，未保存'
      panel = 'none'
      return
    }
    const ok = confirm('保存这条录音？')
    if (!ok) {
      panel = 'none'
      return
    }
    try {
      await putCueRecording({
        lessonId,
        cueId: cue.id,
        blob,
        mime: blob.type || 'audio/webm',
      })
      panel = 'echo-list'
      shadowStep.set('echo')
      await refreshRecordings()
    } catch (e) {
      recordError = e instanceof Error ? e.message : '保存失败'
    }
  }

  function stopRecording() {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') {
      recording = false
      return
    }
    mediaRecorder.stop()
  }
</script>

<div class="overlay" role="presentation">
  <button class="backdrop" type="button" aria-label="关闭解释" onclick={close}></button>

  <div class="sheet" role="dialog" aria-label="解释跟读" tabindex="-1">
    <div class="sheet-top">
      <div class="handle" aria-hidden="true"></div>
      <button class="close" type="button" aria-label="关闭" onclick={close}>×</button>
    </div>

    <div class="scroll">
      <div class="body">
        <CueCard {cue} active />
      </div>
    </div>

    <div class="dock-fixed">
      <div class="modes" role="tablist" aria-label="跟读模式">
        {#each steps as step}
          <button
            class="mode"
            class:active={$shadowStep === step.id}
            type="button"
            role="tab"
            aria-selected={$shadowStep === step.id}
            onclick={() => void onStep(step.id)}
          >
            {step.label}
          </button>
        {/each}
      </div>

      {#if panel === 'echo-list'}
        <div class="panel">
          <div class="panel-head">
            <h3>本句录音</h3>
            <button class="link" type="button" onclick={() => void onStep('speak')}>去录音</button>
          </div>
          {#if listBusy}
            <p class="muted tip">读取中…</p>
          {:else if listError}
            <p class="err">{listError}</p>
          {:else if recordings.length === 0}
            <p class="muted tip">还没有录音。点「说」录一条，或点「去录音」。</p>
          {:else}
            <ul class="rec-list">
              {#each recordings as rec (rec.id)}
                <li>
                  <button class="rec-play" type="button" onclick={() => void playRecording(rec)}>
                    <Icon name="play" size={16} />
                    <span>{rec.name}</span>
                  </button>
                  <button
                    class="rec-del"
                    type="button"
                    aria-label="删除"
                    onclick={() => void removeRecording(rec.id)}>删</button
                  >
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      {/if}

      {#if panel === 'record'}
        <div class="panel record-panel">
          <h3>{recording ? '正在录音…' : '准备录音'}</h3>
          {#if recordError}
            <p class="err">{recordError}</p>
            <button class="action" type="button" onclick={() => void startRecording()}>重试授权</button>
          {:else}
            <div class="wave" aria-hidden="true">
              {#each waveBars as h, i (i)}
                <i style="transform: scaleY({h})"></i>
              {/each}
            </div>
            {#if recording}
              <button class="action danger" type="button" onclick={stopRecording}>停止录制</button>
            {:else if pendingBlob}
              <p class="muted tip">处理中…</p>
            {:else}
              <button class="action" type="button" onclick={() => void startRecording()}>开始录音</button>
            {/if}
          {/if}
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .overlay {
    position: absolute;
    inset: 0;
    z-index: 50;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    overflow: hidden;
  }

  .backdrop {
    position: absolute;
    inset: 0;
    border: 0;
    padding: 0;
    background: rgba(45, 62, 47, 0.28);
    cursor: pointer;
  }

  .sheet {
    position: relative;
    z-index: 1;
    width: 100%;
    max-height: min(88%, 100%);
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
    background: #fff;
    border-radius: 28px 28px 0 0;
    padding: 4px 14px 0;
    box-shadow: 0 -10px 40px rgba(45, 62, 47, 0.12);
    animation: rise 0.22s ease;
    margin-top: auto;
  }

  @keyframes rise {
    from {
      transform: translateY(28px);
    }
    to {
      transform: translateY(0);
    }
  }

  .sheet-top {
    position: relative;
    flex-shrink: 0;
    background: #fff;
    padding-top: 4px;
  }

  .handle {
    width: 40px;
    height: 4px;
    border-radius: 999px;
    background: #d7dece;
    margin: 4px auto 8px;
  }

  .close {
    position: absolute;
    right: 2px;
    top: 2px;
    width: 36px;
    height: 36px;
    border-radius: 999px;
    font-size: 1.35rem;
    line-height: 1;
    color: var(--ink-soft);
    background: var(--bg-sage);
  }

  .scroll {
    flex: 1;
    min-height: 0;
    overflow-x: hidden;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    overscroll-behavior: contain;
    padding-bottom: 8px;
  }

  .body {
    border-radius: var(--radius-lg);
    background: var(--bg-sage);
    padding: 12px;
  }

  .dock-fixed {
    flex-shrink: 0;
    max-height: 48%;
    display: flex;
    flex-direction: column;
    min-height: 0;
    padding-bottom: max(14px, var(--sab));
    background: #fff;
    border-top: 1px solid rgba(45, 62, 47, 0.06);
  }

  .modes {
    flex-shrink: 0;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    padding: 10px 0 8px;
  }

  .mode {
    min-height: 42px;
    border-radius: 12px;
    background: var(--bg-sage);
    color: var(--ink-soft);
    font-weight: 750;
    font-size: 0.9rem;
    position: relative;
    overflow: hidden;
  }

  .mode.active {
    background: #eef6dc;
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

  .panel {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    margin-top: 4px;
    padding: 12px;
    border-radius: 14px;
    background: var(--bg-sage);
  }

  .panel-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 8px;
  }

  .panel h3 {
    margin: 0;
    font-size: 0.88rem;
    font-weight: 800;
  }

  .link {
    font-size: 0.82rem;
    font-weight: 700;
    color: var(--accent-deep);
  }

  .tip {
    margin: 0;
    font-size: 0.85rem;
    line-height: 1.45;
  }

  .err {
    margin: 0 0 8px;
    color: #b42318;
    font-size: 0.85rem;
    font-weight: 650;
  }

  .rec-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .rec-list li {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .rec-play {
    flex: 1;
    min-height: 42px;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 12px;
    border-radius: 12px;
    background: #fff;
    font-weight: 700;
    font-size: 0.88rem;
    text-align: left;
  }

  .rec-del {
    min-height: 42px;
    padding: 0 12px;
    border-radius: 12px;
    background: #f3e6df;
    color: #8a4b2c;
    font-size: 0.8rem;
    font-weight: 700;
  }

  .record-panel {
    text-align: center;
  }

  .wave {
    display: flex;
    align-items: flex-end;
    justify-content: center;
    gap: 3px;
    height: 56px;
    margin: 14px 0 16px;
  }

  .wave i {
    display: block;
    width: 4px;
    height: 100%;
    border-radius: 999px;
    background: var(--accent-deep);
    transform-origin: center bottom;
    opacity: 0.85;
  }

  .action {
    min-height: 44px;
    padding: 0 20px;
    border-radius: 12px;
    background: var(--accent);
    color: var(--accent-ink);
    font-weight: 800;
  }

  .action.danger {
    background: #f3e6df;
    color: #8a4b2c;
  }
</style>
