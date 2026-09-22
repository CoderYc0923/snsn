import type { Cue, CueWord, Lesson, WordTone } from './demo'
import { getApiToken } from './auth'

export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'

export type ApiCueWord = {
  text: string
  furigana?: string | null
  romaji?: string | null
  tone?: string | null
  start_ms?: number | null
  end_ms?: number | null
}

export type ApiCue = {
  id: string
  start_ms: number
  end_ms: number
  text: string
  translation?: string
  words?: ApiCueWord[]
}

export type JobResult = {
  version: number
  source_lang: string
  target_lang: string
  duration_ms: number
  title?: string | null
  cues: ApiCue[]
}

export type JobInfo = {
  id: string
  status: JobStatus
  progress: number
  stage: string
  error: string | null
  result: JobResult | null
  source?: 'upload' | 'bilibili' | string
  title?: string | null
}

export type HealthResponse = {
  ok: boolean
  ffmpeg: boolean
  ytdlp?: boolean
  oss_configured: boolean
  asr_configured: boolean
  busy: boolean
  detail: Record<string, unknown>
}

const envToken = import.meta.env.VITE_SNSN_API_TOKEN as string | undefined

function authHeaders(): HeadersInit {
  const token = getApiToken() || envToken
  if (!token) return {}
  return { 'X-Snsn-Token': token }
}

async function readError(resp: Response): Promise<string> {
  try {
    const data = (await resp.json()) as { detail?: unknown }
    if (typeof data.detail === 'string') return data.detail
    return JSON.stringify(data.detail ?? data)
  } catch {
    return resp.statusText || `HTTP ${resp.status}`
  }
}

async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  const auth = authHeaders()
  for (const [k, v] of Object.entries(auth)) headers.set(k, v)
  return fetch(path, { ...init, headers })
}

/** GET /api/health — no auth required */
export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const resp = await apiFetch('/api/health', { signal })
  if (!resp.ok) throw new Error(await readError(resp))
  return (await resp.json()) as HealthResponse
}

export type AuthVerifyResponse = {
  ok: boolean
  token: string
}

/** POST /api/auth/verify — no auth required */
export async function verifyAccess(password: string, signal?: AbortSignal): Promise<AuthVerifyResponse> {
  const resp = await fetch('/api/auth/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
    signal,
  })
  if (!resp.ok) throw new Error(await readError(resp))
  return (await resp.json()) as AuthVerifyResponse
}

/** POST /api/jobs — multipart audio upload */
export async function createJob(file: File, signal?: AbortSignal): Promise<JobInfo> {
  const body = new FormData()
  body.append('file', file, file.name)
  const resp = await apiFetch('/api/jobs', {
    method: 'POST',
    body,
    signal,
  })
  if (!resp.ok) throw new Error(await readError(resp))
  return (await resp.json()) as JobInfo
}

/** POST /api/jobs/url — Bilibili link */
export async function createJobFromUrl(url: string, signal?: AbortSignal): Promise<JobInfo> {
  const resp = await apiFetch('/api/jobs/url', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
    signal,
  })
  if (!resp.ok) throw new Error(await readError(resp))
  return (await resp.json()) as JobInfo
}

/** GET /api/jobs/{id}/media — retained audio for IndexedDB */
export async function fetchJobMedia(jobId: string, signal?: AbortSignal): Promise<File> {
  const resp = await apiFetch(`/api/jobs/${encodeURIComponent(jobId)}/media`, { signal })
  if (!resp.ok) throw new Error(await readError(resp))
  const blob = await resp.blob()
  const dispo = resp.headers.get('content-disposition') || ''
  const match = /filename\*?=(?:UTF-8''|")?([^\";]+)/i.exec(dispo)
  let name = match?.[1] ? decodeURIComponent(match[1].replace(/"/g, '')) : `snsn-${jobId}.m4a`
  if (!/\.[a-z0-9]+$/i.test(name)) name += '.m4a'
  const type = blob.type || 'audio/mp4'
  return new File([blob], name, { type })
}

/** GET /api/jobs/{id} */
export async function getJob(jobId: string, signal?: AbortSignal): Promise<JobInfo> {
  const resp = await apiFetch(`/api/jobs/${encodeURIComponent(jobId)}`, { signal })
  if (!resp.ok) throw new Error(await readError(resp))
  return (await resp.json()) as JobInfo
}

/** DELETE /api/jobs/{id} */
export async function cancelJob(jobId: string, signal?: AbortSignal): Promise<JobInfo> {
  const resp = await apiFetch(`/api/jobs/${encodeURIComponent(jobId)}`, {
    method: 'DELETE',
    signal,
  })
  if (!resp.ok) throw new Error(await readError(resp))
  return (await resp.json()) as JobInfo
}

/** Best-effort cancel used when closing the import sheet. */
export async function cancelJobSafe(jobId: string): Promise<void> {
  try {
    await cancelJob(jobId)
  } catch {
    // ignore
  }
}

export type PollOptions = {
  intervalMs?: number
  signal?: AbortSignal
  onUpdate?: (job: JobInfo) => void
}

/** Poll GET /api/jobs/{id} until terminal status. */
export async function pollJob(jobId: string, options: PollOptions = {}): Promise<JobInfo> {
  const intervalMs = options.intervalMs ?? 1500
  while (true) {
    if (options.signal?.aborted) {
      throw new DOMException('Aborted', 'AbortError')
    }
    const job = await getJob(jobId, options.signal)
    options.onUpdate?.(job)
    if (job.status === 'succeeded' || job.status === 'failed' || job.status === 'cancelled') {
      return job
    }
    await sleep(intervalMs, options.signal)
  }
}

export function assertReadyForImport(health: HealthResponse, opts?: { needYtdlp?: boolean }): void {
  const missing: string[] = []
  if (!health.ffmpeg) missing.push('ffmpeg')
  if (!health.oss_configured) missing.push('OSS')
  if (!health.asr_configured) missing.push('百炼 API Key')
  if (opts?.needYtdlp && !health.ytdlp) missing.push('yt-dlp')
  if (missing.length) {
    throw new Error(`后端未就绪：缺少 ${missing.join('、')}`)
  }
  if (health.busy) {
    throw new Error('服务端正忙，请稍后再试')
  }
}

/** Map backend pipeline stage → import progress step index (0–3). */
export function stageToImportIndex(stage: string, source: 'upload' | 'bilibili' = 'upload'): number {
  switch (stage) {
    case 'download':
      return source === 'bilibili' ? 0 : 0
    case 'queued':
    case 'starting':
      return 0
    case 'extract':
      return 1
    case 'upload_oss':
    case 'asr':
    case 'split':
      return 2
    case 'translate':
    case 'cleanup':
    case 'done':
      return 3
    default:
      return 0
  }
}

export function mapJobToLesson(
  job: JobInfo,
  file: File,
  opts?: { title?: string },
): Lesson {
  const result = job.result
  if (!result) throw new Error('任务无转写结果')
  const title =
    opts?.title?.trim() ||
    job.title?.trim() ||
    result.title?.trim() ||
    titleFromFilename(file.name)
  return {
    id: job.id,
    title,
    date: new Date().toISOString().slice(0, 10),
    durationMs: result.duration_ms || 0,
    kind: 'audio',
    sourceLang: 'ja',
    targetLang: 'zh-CN',
    posterLabel: posterFromTitle(title),
    cues: result.cues.map(mapCue),
  }
}

function mapCue(cue: ApiCue): Cue {
  return {
    id: cue.id,
    startMs: cue.start_ms,
    endMs: cue.end_ms,
    text: cue.text,
    translation: cue.translation || '',
    words: (cue.words || []).map(mapWord),
  }
}

function mapWord(word: ApiCueWord): CueWord {
  const raw = (word.tone || 'none') as WordTone
  const allowed: WordTone[] = ['yellow', 'blue', 'pink', 'orange', 'mint', 'none']
  return {
    text: word.text,
    furigana: word.furigana || undefined,
    romaji: word.romaji || undefined,
    tone: allowed.includes(raw) ? raw : 'none',
  }
}

function titleFromFilename(name: string): string {
  const base = name.replace(/\.[^.]+$/, '').trim()
  return base || '未命名课程'
}

function posterFromTitle(title: string): string {
  const compact = title.replace(/\s+/g, '')
  return compact.slice(0, 4) || '教材'
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'))
      return
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort)
      resolve()
    }, ms)
    const onAbort = () => {
      clearTimeout(timer)
      reject(new DOMException('Aborted', 'AbortError'))
    }
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}
