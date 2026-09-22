import { openDB, type DBSchema, type IDBPDatabase } from 'idb'
import type { Lesson, SubtitleMode } from './demo'

const DB_NAME = 'snsn'
const DB_VERSION = 2

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
  const tx = db.transaction(['lessons', 'media'], 'readwrite')
  await tx.objectStore('lessons').delete(lessonId)
  await tx.objectStore('media').delete(lessonId)
  await tx.done
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
  const tx = db.transaction('media', 'readwrite')
  await tx.store.clear()
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
