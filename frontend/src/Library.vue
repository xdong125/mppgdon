<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import type { Api, Envelope } from './types'

interface Entry {
  path: string; parent: string; root: string; kind: string; entry_type: string; title: string; year: string
  tmdb_id: string; season: string; episode: string; scraped: boolean | null; nfo_state: string; nfo_path: string
  missing_images: string[]; cms_path: string; present: boolean; checked_at: string
}
interface View {
  roots: {kind: string; mp_path: string; cms_path: string}[]
  summary: Record<string, number>; total: number; page: number; items: Entry[]; config_error: string
  scan: {status: string; entries: number; parsed_nfo: number; reused_nfo: number; skipped_links: number; started_at: string; finished_at: string; errors: string[]}
}
const props = defineProps<{api: Api; pluginId: string}>()
const view = ref<View | null>(null)
const keyword = ref(''), kind = ref(''), entryType = ref('media'), scrape = ref(''), parent = ref('')
const includeMissing = ref(false), page = ref(1), busy = ref(false), starting = ref(false), error = ref('')
const expanded = ref('')
let timer: ReturnType<typeof setTimeout> | undefined
let request: AbortController | undefined
let disposed = false
const scanLabels: Record<string, string> = {idle: '尚未扫描', running: '扫描中', complete: '扫描完成', partial: '部分目录未完成', interrupted: '扫描已中断'}
const imageLabels: Record<string, string> = {poster: '海报', background: '背景图', logo: '标志图', thumbnail: '单集缩略图'}
const typeLabels: Record<string, string> = {directory: '目录', media: '媒体', nfo: 'NFO', image: '图片', other: '其他'}

async function load() {
  clearTimeout(timer)
  request?.abort()
  const current = new AbortController()
  request = current
  busy.value = true
  error.value = ''
  try {
    const result = await props.api.get(`plugin/${props.pluginId}/library`, {feedback: 'silent', signal: current.signal, params: {
      page: page.value, keyword: keyword.value.trim(), kind: kind.value, entry_type: entryType.value,
      scrape: scrape.value, parent: parent.value, include_missing: includeMissing.value,
    }}) as Envelope<View>
    if (disposed || current.signal.aborted) return
    if (!result.success || !result.data) throw new Error(result.message || '无法读取媒体索引。')
    view.value = result.data
    if (view.value.scan.status === 'running') timer = setTimeout(load, 2000)
  } catch (cause) {
    if (!disposed && !current.signal.aborted) error.value = (cause as Error).message || '无法读取媒体索引，请确认管理员权限。'
  } finally {
    if (request === current) busy.value = false
  }
}

function filter() { page.value = 1; expanded.value = ''; void load() }
function browse(path: string) { parent.value = path; entryType.value = ''; scrape.value = ''; filter() }
async function scan() {
  if (starting.value) return
  starting.value = true
  error.value = ''
  try {
    const result = await props.api.post(`plugin/${props.pluginId}/library/scan`, {}, {feedback: 'silent'}) as Envelope<View>
    if (!result.success) throw new Error(result.message || '扫描未启动。')
    if (!disposed) await load()
  } catch (cause) { if (!disposed) error.value = (cause as Error).message || '未收到启动结果，请刷新查看扫描状态。' }
  finally { starting.value = false }
}
function status(item: Entry) {
  if (item.scraped === null) return typeLabels[item.entry_type] ?? item.entry_type
  if (!item.scraped) return item.nfo_state === 'invalid' ? 'NFO 无效，待确认' : '未刮削'
  return item.missing_images.length ? '已刮削 · 图片有缺失' : '已刮削'
}
onMounted(load)
onBeforeUnmount(() => {disposed = true; request?.abort(); clearTimeout(timer)})
</script>

<template>
  <section class="library-page">
    <header class="library-heading">
      <div><h2>媒体库索引</h2><p>手动扫描已配置目录；记录文件与元数据状态。</p></div>
      <div class="library-buttons"><button type="button" :disabled="starting || view?.scan.status === 'running' || !view?.roots.length || !!view?.config_error" @click="scan">{{ starting || view?.scan.status === 'running' ? '扫描中…' : '扫描媒体库' }}</button>
        <button type="button" :disabled="busy" @click="load">刷新</button></div>
    </header>
    <p v-if="error || view?.config_error" role="alert" class="library-error">{{ error || view?.config_error }}</p>
    <template v-if="view">
      <p v-if="!view.roots.length">请先在插件设置中保存电影或电视剧根目录。</p>
      <div class="library-roots">
        <button v-for="root in view.roots" :key="root.mp_path" type="button" @click="browse(root.mp_path)">
          {{ root.kind === 'movie' ? '电影' : '电视剧' }} · {{ root.mp_path }}<small>CMS：{{ root.cms_path }}</small>
        </button>
      </div>
      <p class="library-stats">目录 {{ view.summary.directories ?? 0 }} · 媒体 {{ view.summary.media ?? 0 }} · STRM {{ view.summary.strm ?? 0 }} · 已刮削 {{ view.summary.scraped ?? 0 }} · 未刮削 {{ view.summary.not_scraped ?? 0 }} · 已刮削但缺图 {{ view.summary.incomplete ?? 0 }}</p>
      <p v-if="view.summary.shows" class="scan-state">剧级记录 {{ view.summary.shows }} · 剧级已刮削 {{ view.summary.shows_scraped }}（单集独立统计）</p>
      <p class="scan-state" role="status">{{ scanLabels[view.scan.status] ?? view.scan.status }} · 已扫描 {{ view.scan.entries }} 项 · 本次读取 NFO {{ view.scan.parsed_nfo }} · 复用 NFO {{ view.scan.reused_nfo }}<span v-if="view.scan.skipped_links"> · 跳过链接 {{ view.scan.skipped_links }}</span><span v-if="view.scan.finished_at"> · {{ new Date(view.scan.finished_at).toLocaleString() }}</span></p>
      <p v-for="message in view.scan.errors" :key="message" class="library-error">{{ message }}</p>
      <form class="library-filters" @submit.prevent="filter">
        <input v-model="keyword" aria-label="搜索媒体索引" maxlength="120" placeholder="片名或路径" />
        <select v-model="kind" aria-label="媒体类型" @change="filter"><option value="">全部类型</option><option value="movie">电影</option><option value="tv">电视剧</option></select>
        <select v-model="entryType" aria-label="文件类型" @change="filter"><option value="">全部文件</option><option value="media">媒体 / STRM</option><option value="directory">目录</option><option value="nfo">NFO</option><option value="image">图片</option><option value="other">其他</option></select>
        <select v-model="scrape" aria-label="刮削状态" @change="filter"><option value="">全部状态</option><option value="scraped">已刮削</option><option value="not_scraped">未刮削 / 待确认</option><option value="incomplete">已刮削但缺图</option></select>
        <label><input v-model="includeMissing" type="checkbox" @change="filter" /> 含已移除文件</label>
        <button type="submit">查询</button>
      </form>
      <div v-if="parent" class="library-location"><span>{{ parent }}</span><button type="button" @click="browse('')">返回全部</button><button v-if="!view.roots.some(root => root.mp_path === parent)" type="button" @click="browse(parent.replace(/[\\/][^\\/]+$/, ''))">上一级</button></div>
      <div class="library-list">
        <article v-for="item in view.items" :key="item.path" class="library-row">
          <div class="library-item-text"><button v-if="item.entry_type === 'directory'" type="button" class="directory-link" @click="browse(item.path)">{{ item.title }}</button><strong v-else :title="item.title">{{ item.title }}</strong>
            <small :title="item.path">{{ item.path }}</small></div>
          <span class="library-badge" :class="{scraped:item.scraped, missing: !item.present}">{{ !item.present ? '文件已移除 · ' : '' }}{{ status(item) }}</span>
          <button type="button" :aria-expanded="expanded === item.path" @click="expanded = expanded === item.path ? '' : item.path">详情</button>
          <dl v-if="expanded === item.path" class="library-details">
            <dt>MP 路径</dt><dd>{{ item.path }}</dd><dt>CMS 路径</dt><dd>{{ item.cms_path }}</dd>
            <template v-if="item.nfo_path"><dt>NFO</dt><dd>{{ item.nfo_path }} · {{ item.nfo_state === 'valid' ? '有效' : item.nfo_state === 'missing' ? '未发现' : '无效' }}</dd></template>
            <template v-if="item.tmdb_id"><dt>TMDB ID</dt><dd>{{ item.tmdb_id }}</dd></template>
            <template v-if="item.season || item.episode"><dt>季集</dt><dd>{{ item.season ? `S${item.season.padStart(2,'0')}` : '' }} {{ item.episode ? `E${item.episode.padStart(2,'0')}` : '' }}</dd></template>
            <template v-if="item.missing_images.length"><dt>缺少图片</dt><dd>{{ item.missing_images.map(role => imageLabels[role] ?? role).join('、') }}</dd></template>
            <dt>最后检查</dt><dd>{{ new Date(item.checked_at).toLocaleString() }}</dd>
          </dl>
        </article>
      </div>
      <p v-if="!view.items.length && !busy" class="library-empty">没有符合条件的记录。</p>
      <footer class="library-pagination"><span>共 {{ view.total }} 条 · 第 {{ page }} 页</span><button type="button" :disabled="busy || page <= 1" @click="page--; load()">上一页</button><button type="button" :disabled="busy || page * 50 >= view.total" @click="page++; load()">下一页</button></footer>
    </template>
  </section>
</template>

<style scoped>
.library-page{color:inherit;font:inherit;min-width:0}.library-heading{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.library-heading h2{font-size:20px;margin:0}.library-heading p{font-size:13px;opacity:.7;margin:6px 0 14px}.library-buttons{display:flex;gap:6px}
.library-page button,.library-page input,.library-page select{font:inherit;color:inherit;font-size:13px;background:transparent;border:1px solid rgba(var(--v-theme-on-surface,35,42,56),.2);border-radius:6px;padding:6px 9px}.library-page button{cursor:pointer}.library-page button:disabled{opacity:.45;cursor:default}
.library-roots{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}.library-roots button{text-align:left;overflow-wrap:anywhere}.library-roots small{display:block;opacity:.7;margin-top:3px}.library-stats{font-size:13px}.scan-state{font-size:12px;opacity:.7;overflow-wrap:anywhere}.library-error{font-size:13px;color:rgb(var(--v-theme-error,190,64,64));overflow-wrap:anywhere}
.library-filters{display:flex;gap:6px;flex-wrap:wrap;margin:14px 0}.library-filters input{min-width:0}.library-filters label{display:flex;align-items:center;font-size:12px;gap:3px}.library-filters select{background:rgb(var(--v-theme-surface,255,255,255))}.library-location{display:flex;align-items:center;gap:8px;font-size:12px;margin:8px 0;overflow-wrap:anywhere}
.library-list{display:grid;gap:3px}.library-row{display:grid;grid-template-columns:minmax(0,1fr) auto auto;align-items:center;gap:5px 10px;padding:7px 10px;border:1px solid rgba(var(--v-theme-on-surface,35,42,56),.15);border-radius:6px}.library-item-text{min-width:0}.library-item-text strong,.library-item-text small{display:block;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.library-item-text strong{font-size:13px}.library-item-text small{font-size:11px;opacity:.65;margin-top:3px}.library-badge{font-size:11px;max-width:160px}.library-badge.scraped{color:rgb(var(--v-theme-success,46,140,90))}.library-badge.missing{opacity:.55}.library-page .directory-link{border:0;padding:0;text-align:left;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:rgb(var(--v-theme-primary,111,65,211))}
.library-details{grid-column:1/-1;display:grid;grid-template-columns:5rem minmax(0,1fr);gap:6px;margin:8px 0;font-size:12px}.library-details dt{opacity:.65}.library-details dd{margin:0;overflow-wrap:anywhere}.library-pagination{display:flex;justify-content:flex-end;align-items:center;gap:8px;margin-top:14px;font-size:12px}.library-empty{text-align:center;opacity:.65;padding:20px}
@media(max-width:600px){.library-badge{max-width:84px}.library-row{padding:6px;gap:5px}.library-filters>input{flex:1}}
</style>
