import { get, writable } from 'svelte/store'
import {
  assertReadyForImport,
  cancelJobSafe,
  createJob,
  createJobFromUrl,
  fetchJobMedia,
  getHealth,
  mapJobToLesson,
  pollJob,
  stageToImportIndex,
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
  kind: 'audio'
  source: ImportSource
  stageIndex: number
  progress: number
  status: ImportTaskStatus
  error: string | null
}

export const importTasks = writable<ImportTask[]>([])
export const toastMessage = writable<string | null>(null)

let toastTimer: ReturnType<typeof setTimeout> | null = null
const controllers = new Map<string, AbortController>()
const files = new Map<string, File>()
const urls = new Map<string, string>()

export function stagesForTask(task: ImportTask): readonly string[] {
  return task.source === 'bilibili' ? IMPORT_STAGES_BILI : IMPORT_STAGES_UPLOAD
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

function patchTask(localId: string, patch: Partial<ImportTask>) {
  importTasks.update((all) =>
    all.map((t) => (t.localId === localId ? { ...t, ...patch } : t)),
  )
}

export function dismissImportTask(localId: string) {
  const ctrl = controllers.get(localId)
  if (ctrl) {
    ctrl.abort()
    controllers.delete(localId)
  }
  const task = get(importTasks).find((t) => t.localId === localId)
  if (task?.jobId) void cancelJobSafe(task.jobId)
  files.delete(localId)
  urls.delete(localId)
  importTasks.update((all) => all.filter((t) => t.localId !== localId))
}

export async function startImport(file: File) {
  if (hasRunningImport()) {
    showToast('已有导入任务进行中，请稍后再试')
    return
  }
  if (file.type.startsWith('video/')) {
    showToast('当前仅支持音频，请上传 mp3 / m4a / wav 等')
    return
  }

  const localId = crypto.randomUUID()
  const task: ImportTask = {
    localId,
    jobId: null,
    title: titleFromFilename(file.name),
    kind: 'audio',
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
      progress: created.progress,
    })

    const done = await pollJob(created.id, {
      signal: abort.signal,
      onUpdate: (job) => {
        patchTask(localId, {
          stageIndex: stageToImportIndex(job.stage, 'upload'),
          progress: job.progress,
          title: job.title?.trim() || task.title,
        })
      },
    })

    if (done.status === 'cancelled') {
      throw new Error('任务已取消')
    }
    if (done.status !== 'succeeded' || !done.result) {
      throw new Error(done.error || '转写失败')
    }

    const lesson = mapJobToLesson(done, file)
    if (!lesson.cues.length) {
      throw new Error('未识别到字幕，请换一段更清晰的日语音频')
    }

    await addImportedLesson(lesson, file)
    patchTask(localId, { status: 'succeeded', stageIndex: 3, progress: 1 })
    files.delete(localId)
    controllers.delete(localId)
    importTasks.update((all) => all.filter((t) => t.localId !== localId))
    showToast(`「${lesson.title}」导入完成`)
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      files.delete(localId)
      controllers.delete(localId)
      importTasks.update((all) => all.filter((t) => t.localId !== localId))
      return
    }
    controllers.delete(localId)
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
    showToast('请粘贴 B 站链接')
    return
  }

  const localId = crypto.randomUUID()
  const task: ImportTask = {
    localId,
    jobId: null,
    title: 'B站音频',
    kind: 'audio',
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

    const done = await pollJob(created.id, {
      signal: abort.signal,
      onUpdate: (job) => {
        patchTask(localId, {
          stageIndex: stageToImportIndex(job.stage, 'bilibili'),
          progress: job.progress,
          title: job.title?.trim() || get(importTasks).find((t) => t.localId === localId)?.title || task.title,
        })
      },
    })

    if (done.status === 'cancelled') {
      throw new Error('任务已取消')
    }
    if (done.status !== 'succeeded' || !done.result) {
      throw new Error(done.error || '转写失败')
    }

    const media = await fetchJobMedia(done.id, abort.signal)
    const lesson = mapJobToLesson(done, media, { title: done.title || undefined })
    if (!lesson.cues.length) {
      throw new Error('未识别到字幕，请换一段更清晰的日语音频')
    }

    await addImportedLesson(lesson, media)
    patchTask(localId, { status: 'succeeded', stageIndex: 3, progress: 1 })
    urls.delete(localId)
    controllers.delete(localId)
    importTasks.update((all) => all.filter((t) => t.localId !== localId))
    showToast(`「${lesson.title}」导入完成`)
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      urls.delete(localId)
      controllers.delete(localId)
      importTasks.update((all) => all.filter((t) => t.localId !== localId))
      return
    }
    controllers.delete(localId)
    patchTask(localId, {
      status: 'failed',
      error: err instanceof Error ? err.message : '导入失败',
    })
  }
}

export async function retryImport(localId: string) {
  const file = files.get(localId)
  const url = urls.get(localId)
  if (file) {
    dismissImportTask(localId)
    await startImport(file)
    return
  }
  if (url) {
    dismissImportTask(localId)
    await startImportFromUrl(url)
    return
  }
  showToast('原素材已丢失，请重新导入')
  dismissImportTask(localId)
}
