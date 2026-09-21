import { get, writable } from 'svelte/store'
import {
  type Lesson,
  type RouteName,
  type ShadowStep,
  type SubtitleMode,
} from './demo'
import { buildBackup, downloadBackup, readBackupFile } from './backup'
import {
  clearMediaCache,
  deleteLesson,
  getSettings,
  listLessons,
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
export const echoSheetOpen = writable(false)
export const playing = writable(false)

export async function initStorage() {
  // Drop old UI-preview demo courses if any; home stays empty until real import.
  const existing = await listLessons()
  const demos = existing.filter((l) => l.id.startsWith('demo-'))
  for (const demo of demos) {
    await deleteLesson(demo.id)
  }
  lessons.set(await listLessons())
  const settings = await getSettings()
  subtitleMode.set(settings.subtitleMode)
  storageReady.set(true)
}

export async function persistLessons(next: Lesson[]) {
  lessons.set(next)
  await saveLessons(next)
}

export async function addImportedLesson(lesson: Lesson, file: File) {
  await upsertLesson(lesson)
  await putMediaCache(lesson.id, file, { name: file.name, mime: file.type })
  lessons.update((all) => {
    const rest = all.filter((item) => item.id !== lesson.id)
    // Newest import stays on top within the same date.
    return [lesson, ...rest].sort((a, b) => {
      const byDate = b.date.localeCompare(a.date)
      if (byDate !== 0) return byDate
      if (a.id === lesson.id) return -1
      if (b.id === lesson.id) return 1
      return 0
    })
  })
}

export async function exportBackup() {
  const backup = buildBackup(get(lessons), get(subtitleMode))
  downloadBackup(backup)
  backupMessage.set(`已导出 ${backup.lessons.length} 课（不含原片）`)
}

export async function importBackup(file: File, mode: 'merge' | 'replace' = 'merge') {
  const backup = await readBackupFile(file)
  const incoming = backup.lessons
  if (mode === 'replace') {
    await persistLessons(incoming)
  } else {
    const map = new Map(get(lessons).map((l) => [l.id, l]))
    for (const lesson of incoming) {
      map.set(lesson.id, lesson)
    }
    await persistLessons([...map.values()])
  }
  if (backup.settings?.subtitleMode) {
    subtitleMode.set(backup.settings.subtitleMode)
    await saveSettings({ subtitleMode: backup.settings.subtitleMode })
  }
  backupMessage.set(`已导入 ${incoming.length} 课，请重新选择本地音视频`)
}

export async function removeLesson(lessonId: string) {
  await deleteLesson(lessonId)
  lessons.update((all) => all.filter((l) => l.id !== lessonId))
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
}

export function goHome() {
  unbindMedia()
  route.set('home')
  activeLessonId.set(null)
  echoSheetOpen.set(false)
}

export function goTab(tab: 'home' | 'podcast' | 'settings') {
  activeLessonId.set(null)
  echoSheetOpen.set(false)
  route.set(tab)
}

subtitleMode.subscribe((mode) => {
  if (!get(storageReady)) return
  void saveSettings({ subtitleMode: mode })
})
