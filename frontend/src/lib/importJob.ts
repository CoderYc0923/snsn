import { get, writable } from 'svelte/store'
import {
  assertReadyForImport,
  cancelJobSafe,
  createJob,
  getHealth,
  mapJobToLesson,
  pollJob,
  stageToImportIndex,
} from './api'
import { addImportedLesson } from './nav'

export const IMPORT_STAGES = ['上传', '抽音', '转写', '翻译'] as const

export type ImportTaskStatus = 'running' | 'failed' | 'succeeded'

export type ImportTask = {
  localId: string
  jobId: string | null
  title: string
  kind: 'video' | 'audio'
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
  importTasks.update((all) => all.filter((t) => t.localId !== localId))
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
      stageIndex: stageToImportIndex(created.stage),
      progress: created.progress,
    })

    const done = await pollJob(created.id, {
      signal: abort.signal,
      onUpdate: (job) => {
        patchTask(localId, {
          stageIndex: stageToImportIndex(job.stage),
          progress: job.progress,
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

export async function retryImport(localId: string) {
  const file = files.get(localId)
  if (!file) {
    showToast('原文件已丢失，请重新选择导入')
    dismissImportTask(localId)
    return
  }
  dismissImportTask(localId)
  await startImport(file)
}
