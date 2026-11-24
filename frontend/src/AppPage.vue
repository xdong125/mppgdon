<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import Page from './Page.vue'
import { genres, isMedia, languages, mediaKey, mediaRows, posterUrl, sortOptions } from './tmdb'
import type { Ref } from 'vue'
import type { Media, MediaKind } from './tmdb'
import type { Api } from './types'

const props = defineProps<{ api: Api; pluginId: string }>()
const tab = ref<'tmdb' | 'pansou'>('tmdb')
const kind = ref<MediaKind>('movies')
const sort = ref('popularity.desc'), genre = ref(''), language = ref('')
const rating = ref(0), appliedRating = ref(0)
const input = ref(''), keyword = ref('')
const items = ref<Media[]>([]), page = ref(0), hasMore = ref(false)
const busy = ref(false), error = ref('')
const missingPosters = ref(new Set<string>())
const selected = ref<{ title: string; year: string } | null>(null)
const dialog = ref<HTMLDialogElement | null>(null)
let activeRequest: AbortController | undefined

const filterRows = computed(() => [
  { label: '排序', value: sort, options: sortOptions(kind.value) },
  { label: '风格', value: genre, options: [['', '全部'], ...genres[kind.value]] },
  { label: '语言', value: language, options: [['', '全部'], ...languages] },
])

async function load(nextPage: number) {
  activeRequest?.abort()
  const request = new AbortController()
  activeRequest = request
  busy.value = true
  error.value = ''
  const count = 20
  const searching = Boolean(keyword.value)
  const path = searching ? 'media/search' : `discover/tmdb_${kind.value}`
  const params = searching
    ? { title: keyword.value, type: 'media', media_source: 'themoviedb', page: nextPage, count }
    : { sort_by: sort.value, with_genres: genre.value, with_original_language: language.value,
        vote_average: appliedRating.value, vote_count: 10, page: nextPage }
  try {
    const rows = mediaRows(await props.api.get(path, { params, feedback: 'silent', timeout: 20000, signal: request.signal }))
    if (request.signal.aborted) return
    const known = new Set(items.value.map(mediaKey))
    const unique: Media[] = []
    for (const item of rows.filter(isMedia)) {
      const key = mediaKey(item)
      if (known.has(key)) continue
      known.add(key)
      unique.push(item)
    }
    items.value = [...items.value, ...unique]
    page.value = nextPage
    hasMore.value = rows.length >= count && unique.length > 0
  } catch {
    if (!request.signal.aborted) error.value = 'TMDB 查询失败，请检查 MoviePilot 的 TMDB 连接后重试。'
  } finally {
    if (activeRequest === request) busy.value = false
  }
}

function reload() {
  items.value = []
  page.value = 0
  hasMore.value = false
  missingPosters.value.clear()
  void load(1)
}

function selectKind(value: MediaKind) {
  if (kind.value === value) return
  kind.value = value
  sort.value = 'popularity.desc'
  genre.value = ''
  reload()
}

function selectFilter(filter: Ref<string>, value: string) {
  if (filter.value === value) return
  filter.value = value
  reload()
}

function searchTitles() {
  keyword.value = input.value.trim()
  reload()
}

function clearKeyword() {
  input.value = ''
  searchTitles()
}

async function searchShare(item: Media) {
  const year = String(item.year ?? '')
  selected.value = { title: item.title, year: /^(19|20)\d{2}$/.test(year) ? year : '' }
  await nextTick()
  dialog.value?.showModal()
}

onMounted(reload)
onBeforeUnmount(() => activeRequest?.abort())
</script>

<template>
  <main class="tmdb-page">
    <nav class="page-tabs" aria-label="搜索来源">
      <button type="button" :aria-pressed="tab === 'tmdb'" @click="tab = 'tmdb'">TheMovieDb</button>
      <button type="button" :aria-pressed="tab === 'pansou'" @click="tab = 'pansou'">网盘搜索</button>
    </nav>
    <section v-show="tab === 'tmdb'">
      <form class="title-search" @submit.prevent="searchTitles">
        <input v-model="input" type="search" aria-label="搜索 TMDB 片名" placeholder="搜索电影或电视剧" maxlength="120" />
        <button type="submit">搜索</button>
        <button v-if="input || keyword" type="button" @click="clearKeyword">清除</button>
      </form>

      <div v-if="!keyword" class="tmdb-filters">
        <div class="filter-row" role="group" aria-label="类型">
          <span>类型</span>
          <div class="filter-options">
            <button type="button" :aria-pressed="kind === 'movies'" @click="selectKind('movies')">电影</button>
            <button type="button" :aria-pressed="kind === 'tvs'" @click="selectKind('tvs')">电视剧</button>
          </div>
        </div>
        <div v-for="row in filterRows" :key="row.label" class="filter-row" role="group" :aria-label="row.label">
          <span>{{ row.label }}</span>
          <div class="filter-options">
            <button v-for="[value, name] in row.options" :key="value" type="button"
              :aria-pressed="row.value.value === value" @click="selectFilter(row.value, value)">{{ name }}</button>
          </div>
        </div>
        <label class="filter-row">
          <span>评分</span>
          <span class="rating-track">
            <input v-model.number="rating" type="range" aria-label="最低评分" :aria-valuetext="rating ? `最低 ${rating} 分` : '不限'"
              min="0" max="10" step="0.5" @change="appliedRating = rating; reload()" />
            <output>{{ rating ? `≥ ${rating}` : '不限' }}</output>
          </span>
        </label>
      </div>
      <h2 v-else class="keyword-heading">“{{ keyword }}”的 TMDB 搜索结果</h2>

      <div class="poster-grid" :aria-busy="busy">
        <button v-for="item in items" :key="mediaKey(item)" class="poster-card" type="button"
          :aria-label="`搜索 ${item.title} ${item.year ?? ''} 的网盘资源`" :title="`${item.title} · 搜网盘`" @click="searchShare(item)">
          <div class="poster-art">
            <img v-if="posterUrl(item.poster_path) && !missingPosters.has(mediaKey(item))" :src="posterUrl(item.poster_path)"
              alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" @error="missingPosters.add(mediaKey(item))" />
            <span v-else class="poster-placeholder" aria-hidden="true">{{ item.title }}</span>
            <span class="poster-type">{{ item.type }}</span>
            <span v-if="typeof item.vote_average === 'number' && item.vote_average > 0" class="poster-rating">{{ item.vote_average.toFixed(1) }}</span>
            <span class="poster-action" aria-hidden="true">搜网盘</span>
          </div>
          <div class="poster-caption"><strong>{{ item.title }}</strong><small v-if="item.year">{{ item.year }}</small></div>
        </button>
      </div>
      <div class="page-state" aria-live="polite">
        <p v-if="busy">正在加载…</p>
        <template v-else-if="error"><p role="alert">{{ error }}</p><button type="button" @click="load(page + 1)">重试</button></template>
        <p v-else-if="!items.length">没有找到符合条件的影片。</p>
        <button v-else-if="hasMore" type="button" @click="load(page + 1)">加载更多</button>
      </div>
    </section>
    <Page v-if="tab === 'pansou'" :api="api" :plugin-id="pluginId" embedded />

    <dialog ref="dialog" class="share-dialog" aria-labelledby="mp-share-dialog-title" @close="selected = null">
      <header class="dialog-heading">
        <h2 id="mp-share-dialog-title">{{ selected?.title }} · 网盘资源</h2>
        <form method="dialog"><button type="submit" aria-label="关闭网盘搜索" title="关闭" autofocus>×</button></form>
      </header>
      <Page v-if="selected" :api="api" :plugin-id="pluginId" :initial-media="selected" embedded />
    </dialog>
  </main>
</template>

<style scoped>
.tmdb-page{--tmdb-line:rgba(var(--v-theme-on-surface,35,42,56),.16);--tmdb-accent:rgb(var(--v-theme-primary,111,65,211));padding:18px 24px 36px;min-width:0;color:rgb(var(--v-theme-on-surface,35,42,56));font-family:inherit}
.tmdb-page button,.tmdb-page input{font:inherit;color:inherit}
.tmdb-page button{cursor:pointer}
.page-tabs{display:flex;gap:18px;border-bottom:1px solid var(--tmdb-line);margin-bottom:16px}
.page-tabs button{padding:8px 4px 10px;border:0;border-bottom:3px solid transparent;background:none;font-weight:650}
.page-tabs [aria-pressed="true"]{border-color:var(--tmdb-accent);color:var(--tmdb-accent)}
.title-search{display:flex;gap:6px;max-width:520px;margin-bottom:14px}
.title-search input{min-width:0;flex:1;padding:7px 10px;border:1px solid var(--tmdb-line);border-radius:6px;background:transparent}
.title-search button,.page-state button{padding:7px 12px;border:1px solid var(--tmdb-line);border-radius:6px;background:none;white-space:nowrap}
.title-search button[type="submit"]{background:var(--tmdb-accent);color:#fff;border-color:transparent}
.tmdb-filters{display:grid;gap:7px;padding-bottom:14px}
.filter-row{display:grid;grid-template-columns:3.2rem minmax(0,1fr);align-items:center;gap:7px;font-size:13px}
.filter-row>span:first-child{opacity:.73}
.filter-options{display:flex;gap:5px;overflow-x:auto;padding:2px 2px 3px;scrollbar-width:thin}
.filter-options button{flex:none;padding:4px 9px;border:1px solid transparent;border-radius:5px;background:rgba(var(--v-theme-on-surface,35,42,56),.075);white-space:nowrap}
.filter-options [aria-pressed="true"]{border-color:var(--tmdb-accent);background:rgba(var(--v-theme-primary,111,65,211),.13)}
.rating-track{display:flex;align-items:center;gap:10px}
.rating-track input{flex:1;min-width:0;accent-color:var(--tmdb-accent)}
.rating-track output{width:3.2rem;text-align:right;font-variant-numeric:tabular-nums}
.keyword-heading{font-size:15px;margin:0 0 12px;overflow-wrap:anywhere}
.poster-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,145px),1fr));gap:14px 12px}
.poster-card{min-width:0;border:0;padding:0;background:transparent;text-align:left}
.poster-art{position:relative;display:grid;place-items:center;aspect-ratio:2/3;overflow:hidden;border:1px solid var(--tmdb-line);border-radius:8px;background:rgba(var(--v-theme-on-surface,35,42,56),.065)}
.poster-art img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.poster-placeholder{margin:12px;font-weight:600;text-align:center;overflow-wrap:anywhere}
.poster-type,.poster-rating,.poster-action{position:absolute;color:#fff;background:rgba(15,24,38,.86);padding:3px 6px;border-radius:5px;font-size:11px;font-weight:600}
.poster-type{top:6px;left:6px}.poster-rating{top:6px;right:6px}.poster-action{right:6px;bottom:6px}
.poster-card:hover .poster-action,.poster-card:focus-visible .poster-action{background:var(--tmdb-accent)}
.poster-caption{display:flex;gap:5px;align-items:baseline;padding-top:5px;line-height:1.4}
.poster-caption strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px}
.poster-caption small{margin-left:auto;opacity:.72;font-size:11px}
.page-state{text-align:center;margin:16px 0;font-size:13px}.page-state p{margin:10px 0}
.share-dialog{position:fixed;inset:0;margin:auto;box-sizing:border-box;width:min(940px,calc(100% - 24px));height:fit-content;max-height:calc(100dvh - 48px);padding:0;overflow:auto;border:1px solid var(--tmdb-line);border-radius:8px;color:inherit;background:rgb(var(--v-theme-surface,255,255,255))}
.share-dialog::backdrop{background:rgba(0,0,0,.58)}
.dialog-heading{position:sticky;top:0;z-index:1;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 16px;border-bottom:1px solid var(--tmdb-line);background:inherit}
.dialog-heading h2{margin:0;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:16px}
.dialog-heading button{width:32px;height:32px;border:0;background:transparent;font-size:22px}
@media(max-width:650px){.tmdb-page{padding:12px}.poster-grid{grid-template-columns:repeat(auto-fill,minmax(min(100%,104px),1fr));gap:10px 8px}.filter-row{grid-template-columns:2.5rem minmax(0,1fr)}}
</style>
