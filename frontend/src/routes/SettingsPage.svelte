<script lang="ts">
  import { onMount } from 'svelte'
  import { getHealth, type HealthResponse } from '../lib/api'
  import {
    backupMessage,
    clearLessonMedia,
    exportBackup,
    getLessonCacheSizes,
    importBackup,
    lessons,
    removeLesson,
    subtitleMode,
  } from '../lib/nav'
  import {
    formatBytes,
    getStorageUsage,
    type StorageUsage,
  } from '../lib/storage'
  import BottomNav from '../components/BottomNav.svelte'

  let fileInput: HTMLInputElement
  let busy = $state(false)
  let error = $state<string | null>(null)
  let usage = $state<StorageUsage | null>(null)
  let cacheSizes = $state<Record<string, number>>({})
  let health = $state<HealthResponse | null>(null)
  let healthError = $state<string | null>(null)
  let healthBusy = $state(false)

  async function refreshStorage() {
    usage = await getStorageUsage()
    cacheSizes = await getLessonCacheSizes()
  }

  async function refreshHealth() {
    healthBusy = true
    healthError = null
    try {
      health = await getHealth()
    } catch (e) {
      health = null
      healthError = e instanceof Error ? e.message : '无法连接后端'
    } finally {
      healthBusy = false
    }
  }

  onMount(() => {
    void refreshStorage()
    void refreshHealth()
  })

  function flag(ok: boolean) {
    return ok ? '正常' : '缺失'
  }

  async function onExport() {
    error = null
    busy = true
    try {
      await exportBackup()
    } catch (e) {
      error = e instanceof Error ? e.message : '导出失败'
    } finally {
      busy = false
    }
  }

  async function onPickFile(mode: 'merge' | 'replace') {
    error = null
    const file = fileInput.files?.[0]
    fileInput.value = ''
    if (!file) return
    if (mode === 'replace') {
      const ok = confirm('将用备份覆盖本机全部课单，确定吗？')
      if (!ok) return
    }
    busy = true
    try {
      await importBackup(file, mode)
      await refreshStorage()
    } catch (e) {
      error = e instanceof Error ? e.message : '导入失败'
    } finally {
      busy = false
    }
  }

  function openPicker(mode: 'merge' | 'replace') {
    fileInput.dataset.mode = mode
    fileInput.click()
  }

  function onFileChange() {
    const mode = (fileInput.dataset.mode as 'merge' | 'replace') || 'merge'
    void onPickFile(mode)
  }

  async function onClearCache(id: string, title: string) {
    if (!confirm(`清除「${title}」的原片缓存？字幕会保留。`)) return
    busy = true
    try {
      await clearLessonMedia(id)
      await refreshStorage()
    } finally {
      busy = false
    }
  }

  async function onDeleteLesson(id: string, title: string) {
    if (!confirm(`删除整课「${title}」？字幕与缓存都会移除。`)) return
    busy = true
    try {
      await removeLesson(id)
      await refreshStorage()
    } finally {
      busy = false
    }
  }
</script>

<main class="page settings">
  <header class="page-pad head">
    <h1>设置</h1>
  </header>

  <section class="page-body page-pad">
    <div class="card">
      <div class="card-head">
        <h2>转写服务</h2>
        <button class="linkish" type="button" disabled={healthBusy} onclick={() => refreshHealth()}>
          {healthBusy ? '检查中…' : '刷新'}
        </button>
      </div>
      {#if healthError}
        <p class="err">{healthError}</p>
      {:else if health}
        <ul class="health">
          <li>
            <span>整体</span>
            <strong class:bad={!health.ok}>{health.ok ? '在线' : '异常'}</strong>
          </li>
          <li>
            <span>ffmpeg</span>
            <strong class:bad={!health.ffmpeg}>{flag(health.ffmpeg)}</strong>
          </li>
          <li>
            <span>OSS</span>
            <strong class:bad={!health.oss_configured}>{flag(health.oss_configured)}</strong>
          </li>
          <li>
            <span>百炼 ASR</span>
            <strong class:bad={!health.asr_configured}>{flag(health.asr_configured)}</strong>
          </li>
          <li>
            <span>任务队列</span>
            <strong class:bad={health.busy}>{health.busy ? '忙碌' : '空闲'}</strong>
          </li>
        </ul>
        {#if health.detail?.asr_model}
          <p class="muted tip">模型 {String(health.detail.asr_model)}</p>
        {/if}
      {:else}
        <p class="muted tip">正在检查后端…</p>
      {/if}
    </div>

    <div class="card">
      <h2>本地存储</h2>
      {#if usage}
        <div class="usage tone-{usage.tone}">
          <div class="usage-top">
            <span class="usage-label">已用 {formatBytes(usage.usedBytes)}</span>
            <span class="usage-badge">{usage.label}</span>
          </div>
          <p class="usage-hint">{usage.hint}</p>
        </div>
      {:else}
        <p class="muted tip">正在读取占用…</p>
      {/if}

      <ul class="lesson-clean">
        {#each $lessons as lesson (lesson.id)}
          <li>
            <div class="lesson-meta">
              <strong>{lesson.title}</strong>
              <span class="faint">
                {cacheSizes[lesson.id] ? `缓存 ${formatBytes(cacheSizes[lesson.id])}` : '无原片缓存'}
              </span>
            </div>
            <div class="lesson-actions">
              <button
                type="button"
                disabled={busy || !cacheSizes[lesson.id]}
                onclick={() => onClearCache(lesson.id, lesson.title)}>清缓存</button
              >
              <button
                class="danger"
                type="button"
                disabled={busy}
                onclick={() => onDeleteLesson(lesson.id, lesson.title)}>删整课</button
              >
            </div>
          </li>
        {/each}
      </ul>
    </div>

    <div class="card">
      <h2>默认字幕</h2>
      <div class="modes">
        <button class:active={$subtitleMode === 'ja'} type="button" onclick={() => subtitleMode.set('ja')}
          >原文</button
        >
        <button class:active={$subtitleMode === 'zh'} type="button" onclick={() => subtitleMode.set('zh')}
          >译文</button
        >
        <button
          class:active={$subtitleMode === 'both'}
          type="button"
          onclick={() => subtitleMode.set('both')}>双语</button
        >
      </div>
    </div>

    <div class="card">
      <h2>备份与迁移</h2>
      <p class="muted tip">
        导出为 ZIP：课单、字幕，以及本机已缓存的原片。导入 ZIP 后可直接播放；仍支持旧版 JSON（仅课单字幕）。
      </p>
      <div class="actions">
        <button class="action primary" type="button" disabled={busy} onclick={onExport}>导出备份</button>
        <button class="action" type="button" disabled={busy} onclick={() => openPicker('merge')}
          >导入并合并</button
        >
        <button class="action warn" type="button" disabled={busy} onclick={() => openPicker('replace')}
          >导入并覆盖</button
        >
      </div>
      {#if $backupMessage}
        <p class="ok">{$backupMessage}</p>
      {/if}
      {#if error}
        <p class="err">{error}</p>
      {/if}
      <input
        class="sr-only"
        bind:this={fileInput}
        type="file"
        accept="application/zip,.zip,application/json,.json"
        onchange={onFileChange}
      />
    </div>

    <div class="card">
      <h2>关于</h2>
      <p class="muted">Sn Sn，让你的日语闪闪发光</p>
    </div>
  </section>

  <div class="page-footer">
    <BottomNav />
  </div>
</main>

<style>
  .head {
    flex-shrink: 0;
  }

  .head h1 {
    margin: 12px 0 18px;
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: -0.04em;
  }

  .card {
    background: var(--bg-card);
    border-radius: var(--radius-lg);
    padding: 16px;
    margin-bottom: 12px;
    box-shadow: var(--shadow-card);
  }

  .card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 12px;
  }

  .card-head h2 {
    margin: 0;
  }

  .card h2 {
    margin: 0 0 12px;
    font-size: 0.85rem;
    color: var(--ink-soft);
  }

  .card p {
    margin: 0;
  }

  .linkish {
    font-size: 0.82rem;
    font-weight: 700;
    color: var(--accent-deep);
    min-height: 32px;
    padding: 0 8px;
  }

  .linkish:disabled {
    opacity: 0.5;
  }

  .health {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .health li {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    font-size: 0.9rem;
  }

  .health span {
    color: var(--ink-soft);
  }

  .health strong {
    font-weight: 750;
    color: var(--accent-deep);
  }

  .health strong.bad {
    color: #b42318;
  }

  .tip {
    margin-bottom: 14px !important;
    font-size: 0.9rem;
    line-height: 1.5;
  }

  .usage {
    border-radius: 14px;
    padding: 12px 14px;
    margin-bottom: 14px;
  }

  .usage-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .usage-label {
    font-size: 1.15rem;
    font-weight: 800;
  }

  .usage-badge {
    font-size: 0.75rem;
    font-weight: 750;
    padding: 4px 10px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.55);
  }

  .usage-hint {
    margin-top: 6px !important;
    font-size: 0.85rem;
    font-weight: 600;
    opacity: 0.9;
  }

  .tone-ok {
    background: #e7f5d4;
    color: #3f6b2c;
  }

  .tone-watch {
    background: #f7efc8;
    color: #8a6d12;
  }

  .tone-high {
    background: #f8e0c8;
    color: #9a4e14;
  }

  .tone-critical {
    background: #f8d4d0;
    color: #9b1c1c;
  }

  .lesson-clean {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .lesson-clean li {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 0;
    border-top: 1px solid var(--line);
  }

  .lesson-clean li:first-child {
    border-top: 0;
    padding-top: 0;
  }

  .lesson-meta {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .lesson-meta strong {
    font-size: 0.92rem;
    font-weight: 750;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .lesson-meta span {
    font-size: 0.78rem;
  }

  .lesson-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }

  .lesson-actions button {
    min-height: 38px;
    border-radius: 10px;
    background: var(--bg-sage);
    color: var(--accent-ink);
    font-size: 0.82rem;
    font-weight: 700;
  }

  .lesson-actions button.danger {
    background: #f3e6df;
    color: #8a4b2c;
  }

  .lesson-actions button:disabled {
    opacity: 0.45;
  }

  .modes {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }

  .modes button {
    min-height: 40px;
    border-radius: 12px;
    background: var(--bg-sage);
    color: var(--ink-soft);
    font-weight: 700;
  }

  .modes button.active {
    background: var(--accent);
    color: var(--accent-ink);
  }

  .actions {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .action {
    min-height: 44px;
    border-radius: 12px;
    background: var(--bg-sage);
    color: var(--accent-ink);
    font-weight: 750;
  }

  .action.primary {
    background: var(--accent);
  }

  .action.warn {
    background: #f3e6df;
    color: #8a4b2c;
  }

  .action:disabled {
    opacity: 0.55;
  }

  .ok {
    margin-top: 12px !important;
    color: var(--accent-deep);
    font-size: 0.88rem;
    font-weight: 650;
  }

  .err {
    margin-top: 12px !important;
    color: #b42318;
    font-size: 0.88rem;
    font-weight: 650;
  }
</style>
