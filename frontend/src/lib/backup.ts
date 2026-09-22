import { strFromU8, strToU8, unzip, zip, type Unzipped, type Zippable } from 'fflate'
import type { Lesson, SubtitleMode } from './demo'
import type { MediaCacheRecord } from './storage'

export const BACKUP_FORMAT = 'snsn-backup' as const
export const BACKUP_VERSION = 2

export type BackupMediaMeta = {
  lessonId: string
  name: string
  mime: string
  size: number
  /** Path inside the zip, e.g. media/<lessonId>/payload */
  path: string
}

export type SnSnBackup = {
  format: typeof BACKUP_FORMAT
  version: number
  exportedAt: string
  note: string
  settings?: {
    subtitleMode: SubtitleMode
  }
  lessons: Lesson[]
  media?: BackupMediaMeta[]
}

export type LoadedBackup = {
  backup: SnSnBackup
  /** Media blobs keyed by lessonId (from zip); empty for legacy JSON. */
  mediaByLessonId: Map<string, { blob: Blob; name: string; mime: string }>
}

function mediaPath(lessonId: string): string {
  // Keep path ASCII-safe; original filename lives in manifest.
  return `media/${lessonId}/payload`
}

export function buildBackupManifest(
  lessons: Lesson[],
  subtitleMode: SubtitleMode,
  media: MediaCacheRecord[],
): SnSnBackup {
  const lessonIds = new Set(lessons.map((l) => l.id))
  const included = media.filter((m) => lessonIds.has(m.lessonId))
  const withMedia = included.length
  return {
    format: BACKUP_FORMAT,
    version: BACKUP_VERSION,
    exportedAt: new Date().toISOString(),
    note:
      withMedia > 0
        ? `含 ${withMedia} 课原片缓存；导入后可直接播放。`
        : '未包含原片（本机无对应缓存）；导入后需重新选择音视频。',
    settings: { subtitleMode },
    lessons,
    media: included.map((m) => ({
      lessonId: m.lessonId,
      name: m.name,
      mime: m.mime,
      size: m.size,
      path: mediaPath(m.lessonId),
    })),
  }
}

export function parseBackup(raw: unknown): SnSnBackup {
  if (!raw || typeof raw !== 'object') {
    throw new Error('备份文件无效')
  }
  const data = raw as Partial<SnSnBackup>
  if (data.format !== BACKUP_FORMAT) {
    throw new Error('不是 SnSn 备份文件')
  }
  if (!Array.isArray(data.lessons)) {
    throw new Error('备份缺少课单数据')
  }
  const media = Array.isArray(data.media)
    ? data.media.filter(
        (m): m is BackupMediaMeta =>
          !!m &&
          typeof m === 'object' &&
          typeof m.lessonId === 'string' &&
          typeof m.path === 'string',
      )
    : undefined
  return {
    format: BACKUP_FORMAT,
    version: typeof data.version === 'number' ? data.version : 1,
    exportedAt: data.exportedAt || new Date().toISOString(),
    note: data.note || '',
    settings: data.settings,
    lessons: data.lessons as Lesson[],
    media,
  }
}

async function blobToU8(blob: Blob): Promise<Uint8Array> {
  const buf = await blob.arrayBuffer()
  return new Uint8Array(buf)
}

function unzipAsync(data: Uint8Array): Promise<Unzipped> {
  return new Promise((resolve, reject) => {
    unzip(data, (err, result) => {
      if (err) reject(err)
      else resolve(result)
    })
  })
}

function zipAsync(files: Zippable): Promise<Uint8Array> {
  return new Promise((resolve, reject) => {
    zip(files, (err, result) => {
      if (err) reject(err)
      else resolve(result)
    })
  })
}

export async function buildBackupZip(
  lessons: Lesson[],
  subtitleMode: SubtitleMode,
  media: MediaCacheRecord[],
): Promise<{ blob: Blob; backup: SnSnBackup; mediaCount: number }> {
  const backup = buildBackupManifest(lessons, subtitleMode, media)
  const files: Zippable = {
    'manifest.json': [strToU8(JSON.stringify(backup, null, 2)), { level: 6 }],
  }

  const lessonIds = new Set(lessons.map((l) => l.id))
  let mediaCount = 0
  for (const record of media) {
    if (!lessonIds.has(record.lessonId)) continue
    const path = mediaPath(record.lessonId)
    // Videos/audio are already compressed — store without re-deflating.
    files[path] = [await blobToU8(record.blob), { level: 0 }]
    mediaCount += 1
  }

  const zipped = await zipAsync(files)
  // Copy into a fresh ArrayBuffer-backed view for Blob Part compatibility.
  const copy = new Uint8Array(zipped.byteLength)
  copy.set(zipped)
  return {
    blob: new Blob([copy.buffer], { type: 'application/zip' }),
    backup,
    mediaCount,
  }
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export async function readBackupFile(file: File): Promise<LoadedBackup> {
  const name = file.name.toLowerCase()
  const isZip =
    name.endsWith('.zip') ||
    file.type === 'application/zip' ||
    file.type === 'application/x-zip-compressed'

  if (isZip) {
    return readBackupZip(file)
  }

  // Legacy JSON backup (no media).
  const text = await file.text()
  const backup = parseBackup(JSON.parse(text))
  return { backup, mediaByLessonId: new Map() }
}

async function readBackupZip(file: File): Promise<LoadedBackup> {
  const data = await blobToU8(file)
  const entries = await unzipAsync(data)
  const manifestBytes = entries['manifest.json']
  if (!manifestBytes) {
    throw new Error('备份包缺少 manifest.json')
  }
  const backup = parseBackup(JSON.parse(strFromU8(manifestBytes)))
  const mediaByLessonId = new Map<string, { blob: Blob; name: string; mime: string }>()

  for (const meta of backup.media || []) {
    const bytes = entries[meta.path]
    if (!bytes) continue
    const copy = new Uint8Array(bytes.byteLength)
    copy.set(bytes)
    const mime = meta.mime || 'application/octet-stream'
    mediaByLessonId.set(meta.lessonId, {
      blob: new Blob([copy.buffer], { type: mime }),
      name: meta.name || 'media',
      mime,
    })
  }

  return { backup, mediaByLessonId }
}
