import type { Envelope } from './types'

export type MediaKind = 'movies' | 'tvs'
export interface Media {
  tmdb_id?: number | null
  type: string
  title: string
  year?: string | null
  poster_path?: string | null
  vote_average?: number | null
}

const commonGenres = [
  ['16', '动画'], ['18', '剧情'], ['35', '喜剧'], ['80', '犯罪'], ['99', '纪录片'],
  ['9648', '悬疑'], ['10751', '家庭'], ['37', '西部'],
]
export const genres = {
  movies: [['12', '冒险'], ['14', '奇幻'], ['28', '动作'], ['27', '恐怖'], ['53', '惊悚'],
    ['878', '科幻'], ['36', '历史'], ['10749', '爱情'], ['10402', '音乐'], ['10752', '战争'],
    ['10770', '电视电影'], ...commonGenres],
  tvs: [['10759', '动作冒险'], ['10765', '科幻奇幻'], ['10768', '战争政治'], ['10764', '真人秀'],
    ['10762', '儿童'], ['10763', '新闻'], ['10766', '肥皂剧'], ['10767', '脱口秀'], ...commonGenres],
}
export const languages = [
  ['zh', '中文'], ['en', '英语'], ['ja', '日语'], ['ko', '韩语'], ['fr', '法语'], ['de', '德语'],
  ['es', '西班牙语'], ['it', '意大利语'], ['ru', '俄语'], ['pt', '葡萄牙语'], ['ar', '阿拉伯语'],
  ['hi', '印地语'], ['th', '泰语'],
]

export function sortOptions(kind: MediaKind) {
  const date = kind === 'movies' ? 'release_date' : 'first_air_date'
  const dateLabel = kind === 'movies' ? '上映日期' : '首播日期'
  return [
    ['popularity.desc', '热度降序'], ['popularity.asc', '热度升序'],
    [`${date}.desc`, `${dateLabel}降序`], [`${date}.asc`, `${dateLabel}升序`],
    ['vote_average.desc', '评分降序'], ['vote_average.asc', '评分升序'],
  ]
}

export function mediaRows(response: unknown): unknown[] {
  // 联邦客户端通常返回 envelope；也兼容直接传入宿主解包客户端。
  if (Array.isArray(response)) return response
  const envelope = response as Envelope<unknown> | null
  if (envelope?.success && Array.isArray(envelope.data)) return envelope.data
  throw new Error('TMDB 响应不可用')
}

export function isMedia(row: unknown): row is Media {
  if (!row || typeof row !== 'object') return false
  const item = row as Partial<Media>
  return typeof item.title === 'string' && !!item.title.trim() && item.title.length <= 120
    && (item.type === '电影' || item.type === '电视剧')
}

export function mediaKey(item: Media) {
  return JSON.stringify([item.type, item.tmdb_id ?? [item.title, item.year]])
}

export function posterUrl(path: Media['poster_path']) {
  if (typeof path !== 'string') return ''
  if (/^\/[a-zA-Z0-9]+\.(jpg|png|webp)$/.test(path)) return `https://image.tmdb.org/t/p/w500${path}`
  if (!/^https?:\/\//i.test(path)) return ''
  return path.replace(/^https:\/\/image\.tmdb\.org\/t\/p\/original\//, 'https://image.tmdb.org/t/p/w500/')
}
