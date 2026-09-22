import { openDB, type DBSchema, type IDBPDatabase } from 'idb'
import type { Lesson, SubtitleMode } from './demo'

const DB_NAME = 'snsn'
const DB_VERSION = 3

export type AppSettings = {
  subtitleMode: SubtitleMode
}

export type MediaCacheRecord = {
  lessonId: string
  blob: Blob
  mime: string
  name: string
  size: number
  updatedAt: string
}

export type CueRecording = {
  id: string
  lessonId: string
  cueId: string
  /** Display name: YYYY-MM-DD HH:mm:ss */
  name: string
  blob: Blob
  mime: string
  createdAt: string
}

export type UsageTone = 'ok' | 'watch' | 'high' | 'critical'

export type StorageUsage = {
  usedBytes: number
  tone: UsageTone
  label: string
  hint: string
}

interface SnSnDB extends DBSchema {
  lessons: {
    key: string
    value: Lesson
  }
  media: {
    key: string
    value: MediaCacheRecord
  }
  recordings: {
    key: string
    value: CueRecording
    indexes: {
      'by-lesson': string
      'by-cue': [string, string]
    }
  }
  meta: {
    key: string
    value: AppSettings | { seeded: boolean }
  }
}

let dbPromise: Promise<IDBPDatabase<SnSnDB>> | null = null

function getDb() {
  if (!dbPromise) {
    dbPromise = openDB<SnSnDB>(DB_NAME, DB_VERSION, {
      upgrade(db, oldVersion) {
        if (!db.objectStoreNames.contains('lessons')) {
          db.createObjectStore('lessons', { keyPath: 'id' })
        }
        if (!db.objectStoreNames.contains('meta')) {
          db.createObjectStore('meta')
        }
        if (oldVersion < 2 && !db.objectStoreNames.contains('media')) {
          db.createObjectStore('media', { keyPath: 'lessonId' })
        }
        if (oldVersion < 3 && !db.objectStoreNames.contains('recordings')) {
          const store = db.createObjectStore('recordings', { keyPath: 'id' })
          store.createIndex('by-lesson', 'lessonId')
          store.createIndex('by-cue', ['lessonId', 'cueId'])
        }
      },
    })
  }
  return dbPromise
}

export async function listLessons(): Promise<Lesson[]> {
  const db = await getDb()
  const all = await db.getAll('lessons')
  return all.sort((a, b) => b.date.localeCompare(a.date) || a.title.localeCompare(b.title))
}

export async function saveLessons(lessons: Lesson[]): Promise<void> {
  const db = await getDb()
  const tx = db.transaction('lessons', 'readwrite')
  await tx.store.clear()
  for (const lesson of lessons) {
    await tx.store.put(lesson)
  }
  await tx.done
}

export async function upsertLesson(lesson: Lesson): Promise<void> {
  const db = await getDb()
  await db.put('lessons', lesson)
}

export async function deleteLesson(lessonId: string): Promise<void> {
  const db = await getDb()
  const tx = db.transaction(['lessons', 'media', 'recordings'], 'readwrite')
  await tx.objectStore('lessons').delete(lessonId)
  await tx.objectStore('media').delete(lessonId)
  const recIdx = tx.objectStore('recordings').index('by-lesson')
  let cursor = await recIdx.openCursor(IDBKeyRange.only(lessonId))
  while (cursor) {
    await cursor.delete()
    cursor = await cursor.continue()
  }
  await tx.done
}

export async function putCueRecording(
  input: Omit<CueRecording, 'id' | 'createdAt' | 'name'> & { name?: string },
): Promise<CueRecording> {
  const db = await getDb()
  const createdAt = new Date()
  const record: CueRecording = {
    id: crypto.randomUUID?.() ?? `r-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    lessonId: input.lessonId,
    cueId: input.cueId,
    name: input.name || formatRecordingName(createdAt),
    blob: input.blob,
    mime: input.mime,
    createdAt: createdAt.toISOString(),
  }
  await db.put('recordings', record)
  return record
}

export async function listCueRecordings(lessonId: string, cueId: string): Promise<CueRecording[]> {
  const db = await getDb()
  const rows = await db.getAllFromIndex('recordings', 'by-cue', [lessonId, cueId])
  // Newest first (by createdAt, then display name).
  return rows.sort((a, b) => {
    const byCreated = b.createdAt.localeCompare(a.createdAt)
    if (byCreated !== 0) return byCreated
    return b.name.localeCompare(a.name)
  })
}

export async function deleteCueRecording(id: string): Promise<void> {
  const db = await getDb()
  await db.delete('recordings', id)
}

export async function clearLessonRecordings(lessonId: string): Promise<void> {
  const db = await getDb()
  const tx = db.transaction('recordings', 'readwrite')
  const idx = tx.store.index('by-lesson')
  let cursor = await idx.openCursor(IDBKeyRange.only(lessonId))
  while (cursor) {
    await cursor.delete()
    cursor = await cursor.continue()
  }
  await tx.done
}

export function formatRecordingName(date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())} ${p(date.getHours())}:${p(date.getMinutes())}:${p(date.getSeconds())}`
}

export async function putMediaCache(
  lessonId: string,
  file: Blob,
  meta: { name: string; mime?: string },
): Promise<void> {
  const db = await getDb()
  const record: MediaCacheRecord = {
    lessonId,
    blob: file,
    mime: meta.mime || file.type || 'application/octet-stream',
    name: meta.name,
    size: file.size,
    updatedAt: new Date().toISOString(),
  }
  await db.put('media', record)
}

export async function getMediaCache(lessonId: string): Promise<MediaCacheRecord | undefined> {
  const db = await getDb()
  return db.get('media', lessonId)
}

export async function clearMediaCache(lessonId: string): Promise<void> {
  const db = await getDb()
  await db.delete('media', lessonId)
}

export async function listMediaCaches(): Promise<MediaCacheRecord[]> {
  const db = await getDb()
  return db.getAll('media')
}

export async function clearAllMediaCaches(): Promise<void> {
  const db = await getDb()
  const tx = db.transaction(['media', 'recordings'], 'readwrite')
  await tx.objectStore('media').clear()
  await tx.objectStore('recordings').clear()
  await tx.done
}

export async function listMediaCacheSizes(): Promise<Record<string, number>> {
  const all = await listMediaCaches()
  const map: Record<string, number> = {}
  for (const item of all) {
    map[item.lessonId] = item.size
  }
  return map
}

export async function getSettings(): Promise<AppSettings> {
  const db = await getDb()
  const value = await db.get('meta', 'settings')
  if (value && 'subtitleMode' in value) return value
  return { subtitleMode: 'both' }
}

export async function saveSettings(settings: AppSettings): Promise<void> {
  const db = await getDb()
  await db.put('meta', settings, 'settings')
}

export async function ensureSeeded(seed: Lesson[]): Promise<Lesson[]> {
  const db = await getDb()
  const existing = await db.getAll('lessons')
  if (existing.length > 0) {
    return existing.sort((a, b) => b.date.localeCompare(a.date))
  }

  const flag = await db.get('meta', 'seeded')
  if (flag && 'seeded' in flag && flag.seeded) return []

  const tx = db.transaction(['lessons', 'meta'], 'readwrite')
  for (const lesson of seed) {
    await tx.objectStore('lessons').put(lesson)
  }
  await tx.objectStore('meta').put({ seeded: true }, 'seeded')
  await tx.done
  return seed
}

const GB = 1024 * 1024 * 1024

export function toneForUsedBytes(usedBytes: number): StorageUsage {
  if (usedBytes >= 6 * GB) {
    return {
      usedBytes,
      tone: 'critical',
      label: '偏高',
      hint: '缓存已较多，建议尽快清理不常用课程',
    }
  }
  if (usedBytes >= 3 * GB) {
    return {
      usedBytes,
      tone: 'high',
      label: '偏满',
      hint: '建议清理不常用原片缓存',
    }
  }
  if (usedBytes >= 1 * GB) {
    return {
      usedBytes,
      tone: 'watch',
      label: '渐多',
      hint: '空间还够用，可顺手清掉旧课缓存',
    }
  }
  return {
    usedBytes,
    tone: 'ok',
    label: '充足',
    hint: '本地缓存占用正常',
  }
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < GB) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / GB).toFixed(2)} GB`
}

export async function getStorageUsage(): Promise<StorageUsage> {
  if (navigator.storage?.estimate) {
    const est = await navigator.storage.estimate()
    return toneForUsedBytes(est.usage ?? 0)
  }
  const sizes = await listMediaCacheSizes()
  const used = Object.values(sizes).reduce((a, b) => a + b, 0)
  return toneForUsedBytes(used)
}
