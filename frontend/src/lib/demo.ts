export type SubtitleMode = 'ja' | 'zh' | 'both'
export type ShadowStep = 'listen' | 'echo' | 'speak' | 'playback'
export type RouteName = 'home' | 'lesson' | 'lessons' | 'settings'
export type WordTone = 'yellow' | 'blue' | 'pink' | 'orange' | 'mint' | 'none'

export type CueWord = {
  text: string
  furigana?: string
  romaji?: string
  tone?: WordTone
}

export type Cue = {
  id: string
  startMs: number
  endMs: number
  text: string
  translation: string
  words: CueWord[]
}

export type Lesson = {
  id: string
  title: string
  date: string
  durationMs: number
  kind: 'video' | 'audio'
  sourceLang: 'ja'
  targetLang: 'zh-CN'
  posterLabel: string
  cues: Cue[]
  /** ISO timestamp; used for home "最近使用" and list ordering. */
  lastOpenedAt?: string
}

export const demoLessons: Lesson[] = [
  {
    id: 'demo-dazai',
    title: '[Eng Sub] Chasing Autumn Scenery · 太宰治',
    date: '2024-12-23',
    durationMs: 1156000,
    kind: 'video',
    sourceLang: 'ja',
    targetLang: 'zh-CN',
    posterLabel: '秋の風景',
    cues: [
      {
        id: 'c1',
        startMs: 422000,
        endMs: 428000,
        text: '太宰治は日本の有名な作家です。',
        translation: '太宰治是日本著名作家。',
        words: [
          { text: '太宰', furigana: 'だざい', romaji: 'dazai', tone: 'yellow' },
          { text: '治', furigana: 'おさむ', romaji: 'osamu', tone: 'blue' },
          { text: 'は', romaji: 'wa', tone: 'none' },
          { text: '日本', furigana: 'にほん', romaji: 'nihon', tone: 'pink' },
          { text: 'の', romaji: 'no', tone: 'none' },
          { text: '有名', furigana: 'ゆうめい', romaji: 'yuumei', tone: 'orange' },
          { text: 'な', romaji: 'na', tone: 'none' },
          { text: '作家', furigana: 'さっか', romaji: 'sakka', tone: 'mint' },
          { text: 'です', romaji: 'desu', tone: 'none' },
          { text: '。', tone: 'none' },
        ],
      },
      {
        id: 'c2',
        startMs: 429000,
        endMs: 436000,
        text: '代表作に『人間失格』があります。',
        translation: '代表作有《人间失格》。',
        words: [
          { text: '代表作', furigana: 'だいひょうさく', romaji: 'daihyousaku', tone: 'yellow' },
          { text: 'に', romaji: 'ni', tone: 'none' },
          { text: '『人間失格』', furigana: 'にんげんしっかく', romaji: 'ningen shikkaku', tone: 'blue' },
          { text: 'が', romaji: 'ga', tone: 'none' },
          { text: 'あります', romaji: 'arimasu', tone: 'orange' },
          { text: '。', tone: 'none' },
        ],
      },
      {
        id: 'c3',
        startMs: 437000,
        endMs: 444000,
        text: '今日はいい天気ですね。',
        translation: '今天天气真好啊。',
        words: [
          { text: '今日', furigana: 'きょう', romaji: 'kyou', tone: 'yellow' },
          { text: 'は', romaji: 'wa', tone: 'none' },
          { text: 'いい', romaji: 'ii', tone: 'mint' },
          { text: '天気', furigana: 'てんき', romaji: 'tenki', tone: 'pink' },
          { text: 'です', romaji: 'desu', tone: 'none' },
          { text: 'ね', romaji: 'ne', tone: 'blue' },
          { text: '。', tone: 'none' },
        ],
      },
    ],
  },
  {
    id: 'demo-guide',
    title: 'SnSn 使用说明',
    date: '2024-12-23',
    durationMs: 85000,
    kind: 'audio',
    sourceLang: 'ja',
    targetLang: 'zh-CN',
    posterLabel: 'GUIDE',
    cues: [
      {
        id: 'g1',
        startMs: 0,
        endMs: 4000,
        text: 'まずは動画を取り込んでみましょう。',
        translation: '先试着导入一段视频吧。',
        words: [
          { text: 'まずは', romaji: 'mazu wa', tone: 'none' },
          { text: '動画', furigana: 'どうが', romaji: 'douga', tone: 'yellow' },
          { text: 'を', romaji: 'o', tone: 'none' },
          { text: '取り込んで', furigana: 'とりこんで', romaji: 'torikonde', tone: 'blue' },
          { text: 'みましょう', romaji: 'mimashou', tone: 'mint' },
          { text: '。', tone: 'none' },
        ],
      },
    ],
  },
  {
    id: 'demo-station',
    title: '駅での道案内',
    date: '2024-12-20',
    durationMs: 58000,
    kind: 'video',
    sourceLang: 'ja',
    targetLang: 'zh-CN',
    posterLabel: '駅',
    cues: [
      {
        id: 's1',
        startMs: 800,
        endMs: 3600,
        text: 'すみません、この電車は新宿に行きますか。',
        translation: '不好意思，这趟电车去新宿吗？',
        words: [
          { text: 'すみません', romaji: 'sumimasen', tone: 'yellow' },
          { text: '、', tone: 'none' },
          { text: 'この', romaji: 'kono', tone: 'none' },
          { text: '電車', furigana: 'でんしゃ', romaji: 'densha', tone: 'blue' },
          { text: 'は', romaji: 'wa', tone: 'none' },
          { text: '新宿', furigana: 'しんじゅく', romaji: 'shinjuku', tone: 'orange' },
          { text: 'に', romaji: 'ni', tone: 'none' },
          { text: '行きます', furigana: 'いきます', romaji: 'ikimasu', tone: 'pink' },
          { text: 'か', romaji: 'ka', tone: 'none' },
          { text: '。', tone: 'none' },
        ],
      },
    ],
  },
]
