import type { Lesson, SubtitleMode } from './demo'

export const BACKUP_FORMAT = 'snsn-backup' as const
export const BACKUP_VERSION = 1

export type SnSnBackup = {
  format: typeof BACKUP_FORMAT
  version: number
  exportedAt: string
  note: string
  settings?: {
    subtitleMode: SubtitleMode
  }
  lessons: Lesson[]
}

export function buildBackup(lessons: Lesson[], subtitleMode: SubtitleMode): SnSnBackup {
  return {
    format: BACKUP_FORMAT,
    version: BACKUP_VERSION,
    exportedAt: new Date().toISOString(),
    note: '不含原视频/音频文件。导入后请在本机重新选择对应素材；字幕与课单会恢复。',
    settings: { subtitleMode },
    lessons,
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
  return {
    format: BACKUP_FORMAT,
    version: typeof data.version === 'number' ? data.version : 1,
    exportedAt: data.exportedAt || new Date().toISOString(),
    note: data.note || '',
    settings: data.settings,
    lessons: data.lessons as Lesson[],
  }
}

export function downloadBackup(backup: SnSnBackup): void {
  const blob = new Blob([JSON.stringify(backup, null, 2)], {
    type: 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  const stamp = backup.exportedAt.slice(0, 10)
  a.href = url
  a.download = `snsn-backup-${stamp}.json`
  a.click()
  URL.revokeObjectURL(url)
}

export async function readBackupFile(file: File): Promise<SnSnBackup> {
  const text = await file.text()
  return parseBackup(JSON.parse(text))
}
