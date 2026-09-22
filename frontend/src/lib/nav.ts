import { derived, get, writable } from 'svelte/store'
import {
  type Lesson,
  type RouteName,
  type ShadowStep,
  type SubtitleMode,
} from './demo'
import { buildBackupZip, downloadBlob, readBackupFile } from './backup'
import {
  clearAllMediaCaches,
  clearMediaCache,
  deleteLesson,
  getSettings,
  listLessons,
  listMediaCaches,
  listMediaCacheSizes,
  putMediaCache,
  saveLessons,
  saveSettings,
  upsertLesson,
} from './storage'
import { unbindMedia } from './lessonMedia'

export const route = writable<RouteName>('home')
export const activeLessonId = writable<string | null>(null)
export const lessons = writable<Lesson[]>([])
export const storageReady = writable(false)
export const backupMessage = writable<string | null>(null)

export const cueIndex = writable(0)
export const subtitleMode = writable<SubtitleMode>('both')
export const shadowStep = writable<ShadowStep>('listen')
export const playbackRate = writable(1)
export const loopEnabled = writable(true)
/** When true, cue highlight stays on the selected line (no auto follow). */
export const cuePinned = writable(false)
export const echoSheetOpen = writable(false)
export const playing = writable(false)

/** Most recently opened / imported lesson for the home card. */
export const recentLesson = derived(lessons, ($lessons) => $lessons[0] ?? null)

function recentKey(lesson: Lesson): string {
  return lesson.lastOpenedAt || `${lesson.date}T00:00:00.000Z`
}

export function compareLessonsRecent(a: Lesson, b: Lesson): number {
  const byOpened = recentKey(b).localeCompare(recentKey(a))
  if (byOpened !== 0) return byOpened
  return a.title.localeCompare(b.title)
}

function sortLessonsRecent(items: Lesson[]): Lesson[] {
  return [...items].sort(compareLessonsRecent)
}

export async function initStorage() {
  // Drop old UI-preview demo courses if any; home stays empty until real import.
  const existing = await listLessons()
  const demos = existing.filter((l) => l.id.startsWith('demo-'))
  for (const demo of demos) {
    await deleteLesson(demo.id)
  }
  lessons.set(sortLessonsRecent(await listLessons()))
  const settings = await getSettings()
  subtitleMode.set(settings.subtitleMode)
  storageReady.set(true)
}

export async function persistLessons(next: Lesson[]) {
  const sorted = sortLessonsRecent(next)
  lessons.set(sorted)
  await saveLessons(sorted)
}

export async function addImportedLesson(lesson: Lesson, file: File) {
  const stamped: Lesson = {
    ...lesson,
    lastOpenedAt: new Date().toISOString(),
  }
  await upsertLesson(stamped)
  await putMediaCache(stamped.id, file, { name: file.name, mime: file.type })
  lessons.update((all) => {
    const rest = all.filter((item) => item.id !== stamped.id)
    return sortLessonsRecent([stamped, ...rest])
  })
}

async function markLessonOpened(id: string) {
  const now = new Date().toISOString()
  const all = get(lessons)
  const target = all.find((l) => l.id === id)
  if (!target) return
  const next = all.map((l) => (l.id === id ? { ...l, lastOpenedAt: now } : l))
  await persistLessons(next)
}

export async function exportBackup() {
  const allLessons = get(lessons)
  const media = await listMediaCaches()
  const { blob, backup, mediaCount } = await buildBackupZip(
    allLessons,
    get(subtitleMode),
    media,
  )
  const stamp = backup.exportedAt.slice(0, 10)
  downloadBlob(blob, `snsn-backup-${stamp}.zip`)
  const missing = allLessons.length - mediaCount
  const extra =
    missing > 0 ? `，另有 ${missing} 课无原片缓存未打包` : ''
  backupMessage.set(`已导出 ${backup.lessons.length} 课（含 ${mediaCount} 课原片）${extra}`)
}

export async function importBackup(file: File, mode: 'merge' | 'replace' = 'merge') {
  const { backup, mediaByLessonId } = await readBackupFile(file)
  const incoming = backup.lessons

  if (mode === 'replace') {
    await persistLessons(incoming)
    await clearAllMediaCaches()
  } else {
    const map = new Map(get(lessons).map((l) => [l.id, l]))
    for (const lesson of incoming) {
      map.set(lesson.id, lesson)
    }
    await persistLessons([...map.values()])
  }

  let restored = 0
  for (const lesson of incoming) {
    const media = mediaByLessonId.get(lesson.id)
    if (!media) continue
    await putMediaCache(lesson.id, media.blob, { name: media.name, mime: media.mime })
    restored += 1
  }

  if (backup.settings?.subtitleMode) {
    subtitleMode.set(backup.settings.subtitleMode)
    await saveSettings({ subtitleMode: backup.settings.subtitleMode })
  }

  const mediaNote =
    restored > 0
      ? `，已恢复 ${restored} 课原片`
      : mediaByLessonId.size === 0
        ? '（旧版 JSON 或不含原片，请自行选素材）'
        : ''
  backupMessage.set(`已导入 ${incoming.length} 课${mediaNote}`)
}

export async function removeLesson(lessonId: string) {
  await deleteLesson(lessonId)
  lessons.update((all) => all.filter((l) => l.id !== lessonId))
  backupMessage.set(null)
  if (get(activeLessonId) === lessonId) {
    goHome()
  }
}

export async function clearLessonMedia(lessonId: string) {
  await clearMediaCache(lessonId)
}

export async function getLessonCacheSizes() {
  return listMediaCacheSizes()
}

export function openLesson(id: string) {
  activeLessonId.set(id)
  cueIndex.set(0)
  shadowStep.set('listen')
  echoSheetOpen.set(false)
  playing.set(false)
  route.set('lesson')
  void markLessonOpened(id)
}

export function goHome() {
  unbindMedia()
  route.set('home')
  activeLessonId.set(null)
  echoSheetOpen.set(false)
}

export function goTab(tab: 'home' | 'lessons' | 'settings') {
  unbindMedia()
  activeLessonId.set(null)
  echoSheetOpen.set(false)
  route.set(tab)
}

subtitleMode.subscribe((mode) => {
  if (!get(storageReady)) return
  void saveSettings({ subtitleMode: mode })
})
