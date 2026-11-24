<script setup lang="ts">
import { computed, inject, onMounted, ref } from 'vue'
import type { Api, DuplicateRecord, Envelope, Item, Results, Status, SyncResult } from './types'

const props = defineProps<{
  api: Api; pluginId: string; sourcePluginId?: string; embedded?: boolean
  initialMedia?: {title: string; year: string; kind?: 'movie' | 'tv'; tmdb_id?: number}
}>()
const emit = defineEmits(['close', 'switch', 'action'])
const toast = inject<{success(message: string): unknown} | null>('moviepilot:toast', null)
const keyword = ref(props.initialMedia?.title ?? ''), year = ref(props.initialMedia?.year ?? '')
const mediaType = ref(props.initialMedia?.kind ?? ''), season = ref('')
const qualityOptions = [['original', '原盘'], ['2160p', '4K'], ['1440p', '2K'], ['1080p', '1080/1080p'], ['720p', '720'], ['preview', '抢先版（枪版/含广告）']]
const qualities = ref(['2160p', '1440p', '1080p'])
const status = ref<Status | null>(null), results = ref<Results | null>(null)
const busy = ref(false), error = ref(''), notice = ref(''), searched = ref(false)
const expandedItemId = ref<string | null>(null)
const showDuplicates = ref(false)
const syncingId = ref('')
const syncNotices = ref<Record<string, {status: SyncResult['status']; message: string}>>({})
const visibleDuplicateCount = computed(() => results.value?.items.reduce(
  (count, item) => count + (item.duplicate_records?.length ?? 0), 0,
) ?? 0)

function subtitle(item: Item) {
  return [item.password_conflict ? '提取码冲突' : '', item.quality, item.episode,
    item.collection ? '115 合集' : '115 分享', item.source, item.published].filter(Boolean).join(' · ')
}

function duplicateSubtitle(record: DuplicateRecord) {
  return [record.origin === 'raw' ? '原始结果' : '分组结果', record.quality, record.source, record.published].filter(Boolean).join(' · ')
}

async function loadStatus() {
  try {
    const response = await props.api.get(`plugin/${props.pluginId}/status`, {feedback: 'silent'}) as Envelope<Status>
    if (!response.success || !response.data) throw new Error(response.message || '无法读取插件状态')
    status.value = response.data
    error.value = response.data.config_error
  } catch { error.value = '无法读取插件状态，请重试或检查插件日志。' }
}

async function search() {
  if (busy.value || syncingId.value) return
  error.value = ''; notice.value = ''
  if (!keyword.value.trim()) {error.value = '请输入影视名称。'; return}
  if (year.value && !/^(19|20)\d{2}$/.test(year.value)) {error.value = '年份请输入四位数字。'; return}
  if (!qualities.value.length) {error.value = '请至少选择一种清晰度。'; return}
  if (season.value && !/^\d{1,3}$/.test(season.value)) {error.value = '季号请输入 0～999。'; return}
  busy.value = true; results.value = null; searched.value = false; expandedItemId.value = null
  showDuplicates.value = false
  syncNotices.value = {}
  try {
    const response = await props.api.post(`plugin/${props.pluginId}/search`, {
      keyword: keyword.value.trim(), year: year.value, qualities: qualities.value,
      media_type: mediaType.value, season: season.value && mediaType.value !== 'movie' ? Number(season.value) : null,
      tmdb_id: keyword.value.trim() === props.initialMedia?.title && year.value === props.initialMedia.year && mediaType.value === props.initialMedia.kind ? props.initialMedia.tmdb_id ?? null : null,
    }, {timeout: 65000, feedback: 'silent'}) as Envelope<Results>
    if (!response.success || !response.data) {error.value = response.message || '搜索失败，请重试。'; return}
    results.value = response.data; searched.value = true
  } catch { error.value = '搜索请求失败，请检查 MP 与 PanSou 的连接后重试。' }
  finally { busy.value = false }
}

function canSync(item: Item) {
  const mode = status.value?.sync_mode
  const previous = syncNotices.value[item.id]?.status
  return (mode === 'dry_run' || mode === 'live') && Boolean(item.sync_ticket) && !item.password_conflict
    && previous !== 'accepted' && previous !== 'unknown'
}

async function syncShare(item: Item) {
  if (syncingId.value || !canSync(item)) return
  syncingId.value = item.id
  try {
    const response = await props.api.post(`plugin/${props.pluginId}/share-sync`, {ticket: item.sync_ticket},
      {feedback: 'silent', timeout: 55000}) as Envelope<SyncResult>
    if (!response.success || !response.data?.status) throw new Error()
    syncNotices.value[item.id] = {status: response.data.status, message: response.message}
  } catch (cause) {
    const failure = cause as {status?: number; response?: {status?: number}} | null
    if ((failure?.status ?? failure?.response?.status) === 403) {
      syncNotices.value[item.id] = {status: 'not_sent', message: '权限不足，未提交。仅 MoviePilot 超级管理员可操作。'}
    } else {
      syncNotices.value[item.id] = {status: 'unknown', message: '未收到明确结果，请在 CMS 核对；不会自动重试。'}
    }
  } finally {
    syncingId.value = ''
  }
}

async function copy(item: Item) {
  notice.value = ''; error.value = ''
  if (item.password_conflict) return
  try {
    await navigator.clipboard.writeText(`${item.title}\n${item.url}${item.password ? '\n提取码：' + item.password : ''}`)
    notice.value = '分享信息已复制。'; toast?.success(notice.value)
  } catch { notice.value = '浏览器无法自动复制，请点击“详情”后手动复制。' }
}

async function initialize() {
  await loadStatus()
  if (props.initialMedia && status.value?.enabled && !status.value.config_error) await search()
}

onMounted(initialize)
</script>

<template>
  <section class="mp-search">
    <header v-if="!embedded" class="mp-heading">
      <div><p class="mp-eyebrow">PAN SOU · 115</p><h2>网盘搜索</h2><p>搜索影视资源，核对分享信息。</p></div>
      <div class="mp-actions"><button type="button" @click="emit('switch')">连接设置</button><button type="button" @click="emit('close')">关闭</button></div>
    </header>
    <div v-if="status && !status.enabled" class="mp-alert" role="status">插件尚未启用，请在连接设置中启用并保存。</div>
    <form class="mp-form" :class="{'mp-movie-form': mediaType === 'movie'}" @submit.prevent="search">
      <label>影视名称<input v-model="keyword" name="keyword" maxlength="120" placeholder="例如：无声的回响" :disabled="busy" /></label>
      <label>年份（可选）<input v-model="year" name="year" maxlength="4" inputmode="numeric" placeholder="2026" :disabled="busy" /></label>
      <label>类型<select v-model="mediaType" name="media_type" :disabled="busy"><option value="">自动匹配媒体库</option><option value="movie">电影</option><option value="tv">电视剧</option></select></label>
      <label v-if="mediaType !== 'movie'">季号（可选）<input v-model="season" name="season" maxlength="3" inputmode="numeric" placeholder="自动识别" :disabled="busy" /></label>
      <button class="mp-primary" type="submit" :disabled="busy || !!syncingId || !status?.enabled || !!status?.config_error">{{ busy ? '搜索中…' : '搜索资源' }}</button>
    </form>
    <div class="mp-quality-options" role="group" aria-label="清晰度筛选">
      <span class="mp-muted" title="仅搜索115；画质和季集来自标题，实际内容及链接有效性请自行核实">清晰度</span>
      <label v-for="[value, label] in qualityOptions" :key="value"><input v-model="qualities" type="checkbox" :value="value" :disabled="busy" />{{ label }}</label>
    </div>
    <div v-if="error" class="mp-alert mp-error" role="alert">{{ error }} <button v-if="!status" type="button" @click="initialize">重新连接</button></div>
    <div v-if="notice" class="mp-alert" role="status">{{ notice }}</div>
    <div v-if="busy" class="mp-empty" role="status">正在从 PanSou 搜索，请稍候…</div>
    <template v-if="results">
      <div class="mp-summary-bar">
        <p class="mp-summary">找到 {{ results.items.length }} 个分享 · 合并 {{ results.duplicates }} 次重复 · 过滤 {{ results.filtered }} 条不匹配</p>
        <button v-if="visibleDuplicateCount" class="mp-duplicates-toggle" type="button" :aria-expanded="showDuplicates"
          @click="showDuplicates = !showDuplicates">{{ showDuplicates ? '收起重复' : '展开重复' }}</button>
      </div>
      <p v-if="showDuplicates && visibleDuplicateCount < results.duplicates" class="mp-muted">
        显示 {{ visibleDuplicateCount }} / {{ results.duplicates }} 条重复记录
      </p>
      <p v-if="results.truncated" class="mp-alert">结果较多，仅展示前 200 条。可添加年份或清晰度缩小范围。</p>
      <div class="mp-list">
        <article v-for="item in results.items" :key="item.id" class="mp-row">
          <div class="mp-row-bar">
            <div class="mp-row-text">
              <h3 :title="item.title">{{ item.title }}</h3>
              <p :title="item.sync_target ? `同步至：${item.sync_target.cms_path} · ${subtitle(item)}` : item.sync_error || subtitle(item)">{{ item.sync_target ? `同步至：${item.sync_target.cms_path}` : item.sync_error || subtitle(item) }}</p>
            </div>
            <div class="mp-row-actions">
              <button type="button" class="mp-sync" :disabled="!!syncingId || !canSync(item)"
                :title="item.sync_error || status?.sync_error || (status?.sync_mode === 'unavailable' ? '请先保存 CMS 分享同步设置' : item.sync_target?.cms_path)"
                @click="syncShare(item)">{{ syncingId === item.id ? '提交中…' : status?.sync_mode === 'dry_run' ? '演练同步' : '分享同步' }}</button>
              <button type="button" title="分享信息" aria-label="分享信息"
                :aria-expanded="expandedItemId === item.id"
                @click="expandedItemId = expandedItemId === item.id ? null : item.id">详情</button>
              <button type="button" title="复制分享" aria-label="复制分享" :disabled="item.password_conflict" @click="copy(item)">复制</button>
              <a v-if="!item.password_conflict" title="打开分享" aria-label="打开分享" :href="item.url"
                target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">打开 ↗</a>
            </div>
          </div>
          <p v-if="syncNotices[item.id]" class="mp-sync-notice" role="status">{{ syncNotices[item.id].message }}</p>
          <div v-if="expandedItemId === item.id" class="mp-details">
            <p>{{ item.title }}</p>
            <template v-if="item.sync_target"><p>MP 目标：{{ item.sync_target.mp_path }}</p><p>CMS 目标：{{ item.sync_target.cms_path }} · {{ item.sync_target.reason }}</p></template>
            <p v-if="item.password_conflict" class="mp-warning">同一分享存在不同提取码，请手动核对，已禁用快捷操作。</p>
            <p class="mp-share">{{ item.url }}</p>
            <p>提取码：{{ item.password || '未提供' }}</p>
          </div>
          <ul v-if="showDuplicates && item.duplicate_records?.length" class="mp-duplicates" aria-label="同一分享的重复记录">
            <li v-for="(record, index) in item.duplicate_records" :key="index" class="mp-duplicate mp-row-text">
              <p class="mp-duplicate-title" :title="record.title">{{ record.title }}</p>
              <p :title="duplicateSubtitle(record)">{{ duplicateSubtitle(record) }}</p>
            </li>
          </ul>
        </article>
      </div>
    </template>
    <div v-if="searched && !results?.items.length" class="mp-empty">未找到匹配的 115 分享，可调整关键词或筛选条件后重试。</div>
    <div v-if="!searched && !busy && !error" class="mp-empty">输入片名，开始第一次搜索。</div>
  </section>
</template>

<style scoped>
.mp-search{padding:24px;color:rgb(var(--v-theme-on-surface,35,42,56));font-family:inherit}.mp-heading,.mp-actions{display:flex;justify-content:space-between;align-items:center;gap:12px}.mp-heading{align-items:flex-start;margin-bottom:24px}.mp-heading h2{font-size:28px;margin:0 0 6px}.mp-heading p{margin:0}.mp-eyebrow{font-size:11px;letter-spacing:2px;opacity:.65;padding-bottom:8px}.mp-form{display:grid;grid-template-columns:minmax(180px,1fr) 120px 150px auto;gap:12px;align-items:end}.mp-form label{font-size:13px;display:grid;gap:7px}.mp-search input,.mp-search select{width:100%;padding:11px 12px;border:1px solid rgba(var(--v-theme-on-surface,35,42,56),.23);border-radius:8px;background:rgb(var(--v-theme-surface,255,255,255));color:inherit;font:inherit}.mp-search button,.mp-search a{font:inherit;font-size:13px;padding:10px 14px;border-radius:8px;border:1px solid rgba(var(--v-theme-on-surface,35,42,56),.2);background:transparent;color:inherit;cursor:pointer;text-decoration:none}.mp-search button:disabled{opacity:.45;cursor:default}.mp-search .mp-primary{background:rgb(var(--v-theme-primary,75,102,225));color:white;border-color:transparent;min-height:43px}.mp-muted{font-size:12px;opacity:.65;overflow-wrap:anywhere}.mp-summary{font-size:13px;margin:24px 0 14px}.mp-share{word-break:break-all;user-select:text}.mp-empty{text-align:center;padding:48px 12px;opacity:.65}.mp-alert{padding:12px 16px;margin:14px 0;background:rgba(80,120,200,.1);border-radius:8px;font-size:13px}.mp-error{background:rgba(200,60,60,.12)}.mp-warning{color:#b7791f}.mp-search input:focus,.mp-search select:focus{outline:2px solid rgb(var(--v-theme-primary,75,102,225));outline-offset:2px}@media(max-width:650px){.mp-search{padding:16px}.mp-form{grid-template-columns:1fr 1fr}.mp-form label:first-child{grid-column:1/-1}.mp-primary{grid-column:1/-1}.mp-heading{flex-wrap:wrap}}

.mp-list{display:grid;gap:3px}
.mp-search .mp-form{grid-template-columns:minmax(130px,1fr) 100px 135px 100px auto}
.mp-search .mp-movie-form{grid-template-columns:minmax(130px,1fr) 100px 135px auto}
.mp-quality-options{display:flex;align-items:center;gap:8px 16px;overflow-x:auto;padding:10px 0 2px;white-space:nowrap;font-size:13px}
.mp-quality-options label{display:inline-flex;align-items:center;gap:5px;flex:none;cursor:pointer}
.mp-search .mp-quality-options input{width:auto;margin:0;padding:0;accent-color:rgb(var(--v-theme-primary,75,102,225))}
@media(max-width:650px){.mp-search .mp-form{grid-template-columns:1fr 1fr}.mp-search .mp-form label:first-child{grid-column:1/-1}}
.mp-summary-bar{display:flex;align-items:center;flex-wrap:wrap;gap:8px 12px;margin:20px 0 10px}
.mp-summary-bar .mp-summary{margin:0}
.mp-summary-bar .mp-duplicates-toggle{padding:4px 8px;border-radius:5px;font-size:12px}
.mp-duplicates{list-style:none;margin:0 10px 0 16px;padding:0 4px 4px 10px;border-inline-start:2px solid rgba(var(--v-theme-on-surface,35,42,56),.18)}
.mp-duplicate{padding:4px 0}
.mp-duplicate .mp-duplicate-title{font-size:13px;font-weight:600;opacity:1}
.mp-row{min-width:0;border-radius:6px;box-shadow:inset 0 0 0 1px rgba(var(--v-theme-on-surface,35,42,56),.14)}
.mp-row-bar{box-sizing:border-box;display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:8px;height:48px;padding:0 8px 0 10px}
.mp-row-text h3,.mp-row-text p{margin:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mp-row-text h3{font-size:14px;line-height:18px;font-weight:600}
.mp-row-text p{font-size:12px;line-height:16px;opacity:.7}
.mp-row-actions{display:flex;gap:4px;align-items:center;white-space:nowrap}
.mp-row-actions button,.mp-row-actions a{box-sizing:border-box;display:inline-flex;align-items:center;justify-content:center;height:28px;padding:0 6px;line-height:1;border-radius:5px;font-size:12px}
.mp-row-actions .mp-sync{inline-size:4.6rem}
.mp-sync-notice{margin:0;padding:0 10px 8px;font-size:12px;overflow-wrap:anywhere}
.mp-row-actions button:not(:disabled):hover,.mp-row-actions a:hover,.mp-row-actions [aria-expanded="true"]{background:rgba(var(--v-theme-on-surface,35,42,56),.08)}
.mp-details{padding:7px 10px 9px;border-top:1px solid rgba(var(--v-theme-on-surface,35,42,56),.14);font-size:12px;overflow-wrap:anywhere}
.mp-details p{margin:2px 0}
</style>
