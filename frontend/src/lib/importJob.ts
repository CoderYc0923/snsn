import { get, writable } from 'svelte/store'
import {
  assertReadyForImport,
  cancelJobSafe,
  createJob,
  createJobFromUrl,
  fetchJobMedia,
  getHealth,
  getJob,
  mapJobToLesson,
  pollJob,
  stageToImportIndex,
  type JobInfo,
} from './api'
import { addImportedLesson } from './nav'

export const IMPORT_STAGES_UPLOAD = ['上传', '抽音', '转写', '翻译'] as const
export const IMPORT_STAGES_BILI = ['下载', '抽音', '转写', '翻译'] as const

/** @deprecated use stagesForTask */
export const IMPORT_STAGES = IMPORT_STAGES_UPLOAD

export type ImportTaskStatus = 'running' | 'failed' | 'succeeded'
export type ImportSource = 'upload' | 'bilibili'

export type ImportTask = {
  localId: string
  jobId: string | null
  title: string
  kind: 'audio' | 'video'
  source: ImportSource
  stageIndex: number
  progress: number
  status: ImportTaskStatus
  error: string | null
}

type PersistedPending = {
  localId: string
  jobId: string
  title: string
  kind: 'audio' | 'video'
  source: ImportSource
  url?: string
  createdAt: number
  stageIndex: number
  progress: number
}

const PENDING_KEY = 'snsn.import.pending.v1'
const PENDING_TTL_MS = 24 * 60 * 60 * 1000

export const importTasks = writable<ImportTask[]>([])
export const toastMessage = writable<string | null>(null)

let toastTimer: ReturnType<typeof setTimeout> | null = null
const controllers = new Map<string, AbortController>()
const files = new Map<string, File>()
const urls = new Map<string, string>()
let resumeBusy = false

export function stagesForTask(task: ImportTask): readonly string[] {
  return task.source === 'bilibili' ? IMPORT_STAGES_BILI : IMPORT_STAGES_UPLOAD
}

/** Normalize Bilibili download failures into a clear login/VIP tip. */
export function formatImportError(err: unknown, source: ImportSource = 'upload'): string {
  const raw = err instanceof Error ? err.message : String(err || '导入失败')
  if (source !== 'bilibili') return raw || '导入失败'

  if (
    /该链接需要登录|需要登录|大会员|SNSN_BILIBILI_COOKIE|SESSDATA|付费|专享|权限不足|HTTP 412|Precondition|cookie/i.test(
      raw,
    )
  ) {
    return (
      '该链接需要登录或大会员才能下载。' +
      '请换公开可播的稿件，或在服务器配置 B 站 Cookie（SNSN_BILIBILI_COOKIE_FILE，含 SESSDATA）后重试。'
    )
  }
  return raw || '导入失败'
}

export function showToast(message: string, ms = 4200) {
  toastMessage.set(message)
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastMessage.set(null)
    toastTimer = null
  }, ms)
}

export function clearToast() {
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = null
  toastMessage.set(null)
}

export function hasRunningImport() {
  return get(importTasks).some((t) => t.status === 'running')
}

function titleFromFilename(name: string) {
  return name.replace(/\.[^.]+$/, '').trim() || '未命名课程'
}

function readPending(): PersistedPending[] {
  try {
    const raw = localStorage.getItem(PENDING_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as PersistedPending[]
    if (!Array.isArray(parsed)) return []
    const now = Date.now()
    return parsed.filter(
      (p) =>
        p &&
        typeof p.jobId === 'string' &&
        typeof p.localId === 'string' &&
        now - (p.createdAt || 0) < PENDING_TTL_MS,
    )
  } catch {
    return []
  }
}

function writePending(rows: PersistedPending[]) {
  try {
    localStorage.setItem(PENDING_KEY, JSON.stringify(rows))
  } catch {
    // quota / private mode
  }
}

function upsertPending(row: PersistedPending) {
  const all = readPending().filter((p) => p.localId !== row.localId && p.jobId !== row.jobId)
  all.unshift(row)
  writePending(all)
}

function removePending(localId: string) {
  writePending(readPending().filter((p) => p.localId !== localId))
}

function persistRunning(localId: string) {
  const task = get(importTasks).find((t) => t.localId === localId)
  if (!task?.jobId || task.status !== 'running') return
  upsertPending({
    localId: task.localId,
    jobId: task.jobId,
    title: task.title,
    kind: task.kind,
    source: task.source,
    url: urls.get(localId),
    createdAt: Date.now(),
    stageIndex: task.stageIndex,
    progress: task.progress,
  })
}

function patchTask(localId: string, patch: Partial<ImportTask>) {
  importTasks.update((all) =>
    all.map((t) => (t.localId === localId ? { ...t, ...patch } : t)),
  )
  const next = get(importTasks).find((t) => t.localId === localId)
  if (next?.jobId && next.status === 'running') {
    persistRunning(localId)
  }
}

export function dismissImportTask(localId: string) {
  const ctrl = controllers.get(localId)
  if (ctrl) {
    ctrl.abort()
    controllers.delete(localId)
  }
  const task = get(importTasks).find((t) => t.localId === localId)
  if (task?.jobId && task.status === 'running') void cancelJobSafe(task.jobId)
  files.delete(localId)
  urls.delete(localId)
  removePending(localId)
  importTasks.update((all) => all.filter((t) => t.localId !== localId))
}

async function finishSucceeded(
  localId: string,
  done: JobInfo,
  opts: { kind: 'audio' | 'video'; source: ImportSource; file?: File },
  signal: AbortSignal,
) {
  const file = opts.file ?? (await fetchJobMedia(done.id, signal))
  const lesson = mapJobToLesson(done, file, {
    title: done.title || undefined,
    kind: opts.kind,
  })
  if (!lesson.cues.length) {
    throw new Error('未识别到字幕，请换一段更清晰的日语材料')
  }
  await addImportedLesson(lesson, file)
  patchTask(localId, { status: 'succeeded', stageIndex: 3, progress: 1 })
  files.delete(localId)
  urls.delete(localId)
  controllers.delete(localId)
  removePending(localId)
  importTasks.update((all) => all.filter((t) => t.localId !== localId))
  showToast(`「${lesson.title}」导入完成`)
}

async function followJob(localId: string, jobId: string, source: ImportSource, kind: 'audio' | 'video') {
  const abort = new AbortController()
  controllers.set(localId, abort)
  try {
    const done = await pollJob(jobId, {
      signal: abort.signal,
      onUpdate: (job) => {
        patchTask(localId, {
          stageIndex: stageToImportIndex(job.stage, source),
          progress: job.progress,
          title:
            job.title?.trim() ||
            get(importTasks).find((t) => t.localId === localId)?.title ||
            (source === 'bilibili' ? 'B站视频' : '导入中'),
        })
      },
    })

    if (done.status === 'cancelled') {
      throw new Error('任务已取消')
    }
    if (done.status !== 'succeeded' || !done.result) {
      throw new Error(done.error || '转写失败')
    }

    await finishSucceeded(
      localId,
      done,
      { kind, source, file: files.get(localId) },
      abort.signal,
    )
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      files.delete(localId)
      urls.delete(localId)
      controllers.delete(localId)
      // Keep pending if user only backgrounded; dismissImportTask clears explicitly.
      if (!get(importTasks).some((t) => t.localId === localId)) {
        removePending(localId)
      }
      return
    }
    controllers.delete(localId)
    removePending(localId)
    patchTask(localId, {
      status: 'failed',
      error: formatImportError(err, source),
    })
  }
}

/** Restore in-flight server jobs after refresh / returning to the tab. */
export async function resumePendingImports() {
  if (resumeBusy) return
  resumeBusy = true
  try {
    const pending = readPending()
    writePending(pending)
    for (const row of pending) {
      if (controllers.has(row.localId)) continue
      if (get(importTasks).some((t) => t.localId === row.localId || t.jobId === row.jobId)) {
        const existing = get(importTasks).find(
          (t) => t.localId === row.localId || t.jobId === row.jobId,
        )
        if (existing?.status === 'running' && existing.jobId && !controllers.has(existing.localId)) {
          void followJob(existing.localId, existing.jobId, existing.source, existing.kind)
        }
        continue
      }

      if (row.url) urls.set(row.localId, row.url)

      let job: JobInfo
      try {
        job = await getJob(row.jobId)
      } catch {
        removePending(row.localId)
        importTasks.update((all) => [
          {
            localId: row.localId,
            jobId: row.jobId,
            title: row.title,
            kind: row.kind,
            source: row.source,
            stageIndex: row.stageIndex,
            progress: row.progress,
            status: 'failed',
            error: '任务已过期或服务器已清理，请重新导入',
          },
          ...all.filter((t) => t.localId !== row.localId),
        ])
        continue
      }

      const task: ImportTask = {
        localId: row.localId,
        jobId: row.jobId,
        title: job.title?.trim() || row.title,
        kind: row.kind,
        source: row.source,
        stageIndex: stageToImportIndex(job.stage, row.source),
        progress: job.progress,
        status: 'running',
        error: null,
      }

      if (job.status === 'succeeded' && job.result) {
        importTasks.update((all) => [task, ...all.filter((t) => t.localId !== task.localId)])
        const abort = new AbortController()
        controllers.set(row.localId, abort)
        try {
          await finishSucceeded(
            row.localId,
            job,
            { kind: row.kind, source: row.source },
            abort.signal,
          )
        } catch (err) {
          controllers.delete(row.localId)
          removePending(row.localId)
          patchTask(row.localId, {
            status: 'failed',
            error: formatImportError(err, row.source),
          })
        }
        continue
      }

      if (job.status === 'failed' || job.status === 'cancelled') {
        removePending(row.localId)
        importTasks.update((all) => [
          {
            ...task,
            status: 'failed',
            error:
              job.status === 'cancelled'
                ? '任务已取消'
                : formatImportError(job.error || '转写失败', row.source),
          },
          ...all.filter((t) => t.localId !== task.localId),
        ])
        continue
      }

      importTasks.update((all) => [task, ...all.filter((t) => t.localId !== task.localId)])
      void followJob(row.localId, row.jobId, row.source, row.kind)
    }
  } finally {
    resumeBusy = false
  }
}

export async function startImport(file: File) {
  if (hasRunningImport()) {
    showToast('已有导入任务进行中，请稍后再试')
    return
  }

  const localId = crypto.randomUUID()
  const kind: ImportTask['kind'] = file.type.startsWith('video/') ? 'video' : 'audio'
  const task: ImportTask = {
    localId,
    jobId: null,
    title: titleFromFilename(file.name),
    kind,
    source: 'upload',
    stageIndex: 0,
    progress: 0,
    status: 'running',
    error: null,
  }

  files.set(localId, file)
  importTasks.update((all) => [task, ...all])

  const abort = new AbortController()
  controllers.set(localId, abort)

  try {
    const health = await getHealth(abort.signal)
    assertReadyForImport(health)

    const created = await createJob(file, abort.signal)
    patchTask(localId, {
      jobId: created.id,
      stageIndex: stageToImportIndex(created.stage, 'upload'),
      progress: Math.max(created.progress, created.status === 'succeeded' ? 1 : 0.02),
      title: created.title?.trim() || task.title,
    })
    persistRunning(localId)

    // Content-cache hit may already be finished.
    if (created.status === 'succeeded' && created.result) {
      await finishSucceeded(localId, created, { kind, source: 'upload', file }, abort.signal)
      return
    }

    controllers.delete(localId)
    await followJob(localId, created.id, 'upload', kind)
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      files.delete(localId)
      controllers.delete(localId)
      removePending(localId)
      importTasks.update((all) => all.filter((t) => t.localId !== localId))
      return
    }
    controllers.delete(localId)
    removePending(localId)
    patchTask(localId, {
      status: 'failed',
      error: err instanceof Error ? err.message : '导入失败',
    })
  }
}

export async function startImportFromUrl(url: string) {
  if (hasRunningImport()) {
    showToast('已有导入任务进行中，请稍后再试')
    return
  }
  const trimmed = url.trim()
  if (!trimmed) {
    showToast('请粘贴 B 站分享内容或链接')
    return
  }

  const localId = crypto.randomUUID()
  const task: ImportTask = {
    localId,
    jobId: null,
    title: 'B站视频',
    kind: 'video',
    source: 'bilibili',
    stageIndex: 0,
    progress: 0,
    status: 'running',
    error: null,
  }

  urls.set(localId, trimmed)
  importTasks.update((all) => [task, ...all])

  const abort = new AbortController()
  controllers.set(localId, abort)

  try {
    const health = await getHealth(abort.signal)
    assertReadyForImport(health, { needYtdlp: true })

    const created = await createJobFromUrl(trimmed, abort.signal)
    patchTask(localId, {
      jobId: created.id,
      stageIndex: stageToImportIndex(created.stage, 'bilibili'),
      progress: Math.max(0.02, created.progress),
      title: created.title?.trim() || task.title,
    })
    persistRunning(localId)

    if (created.status === 'succeeded' && created.result) {
      await finishSucceeded(localId, created, { kind: 'video', source: 'bilibili' }, abort.signal)
      return
    }

    controllers.delete(localId)
    await followJob(localId, created.id, 'bilibili', 'video')
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      urls.delete(localId)
      controllers.delete(localId)
      removePending(localId)
      importTasks.update((all) => all.filter((t) => t.localId !== localId))
      return
    }
    controllers.delete(localId)
    removePending(localId)
    patchTask(localId, {
      status: 'failed',
      error: formatImportError(err, 'bilibili'),
    })
  }
}

export async function retryImport(localId: string) {
  const file = files.get(localId)
  const url = urls.get(localId)
  const task = get(importTasks).find((t) => t.localId === localId)
  if (file) {
    dismissImportTask(localId)
    await startImport(file)
    return
  }
  if (url || task?.source === 'bilibili') {
    const link = url || readPending().find((p) => p.localId === localId)?.url
    dismissImportTask(localId)
    if (link) {
      await startImportFromUrl(link)
      return
    }
  }
  showToast('原素材已丢失，请重新导入')
  dismissImportTask(localId)
}
