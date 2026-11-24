<script setup lang="ts">
import { inject, onMounted, ref } from 'vue'
import type { Api, Envelope, Item, Results, Status } from './types'

const props = defineProps<{api: Api; pluginId: string; sourcePluginId?: string}>()
const emit = defineEmits(['close', 'switch', 'action'])
const toast = inject<{success(message: string): unknown} | null>('moviepilot:toast', null)
const keyword = ref(''), year = ref(''), resolution = ref('all')
const status = ref<Status | null>(null), results = ref<Results | null>(null)
const busy = ref(false), error = ref(''), notice = ref(''), searched = ref(false)

async function loadStatus() {
  try {
    const response = await props.api.get(`plugin/${props.pluginId}/status`, {feedback: 'silent'}) as Envelope<Status>
    if (!response.success || !response.data) throw new Error(response.message || '无法读取插件状态')
    status.value = response.data
    error.value = response.data.config_error
  } catch { error.value = '无法读取插件状态，请重试或检查插件日志。' }
}

async function search() {
  if (busy.value) return
  error.value = ''; notice.value = ''
  if (!keyword.value.trim()) {error.value = '请输入影视名称。'; return}
  if (year.value && !/^(19|20)\d{2}$/.test(year.value)) {error.value = '年份请输入四位数字。'; return}
  busy.value = true; results.value = null; searched.value = false
  try {
    const response = await props.api.post(`plugin/${props.pluginId}/search`, {
      keyword: keyword.value.trim(), year: year.value, resolution: resolution.value,
    }, {timeout: 65000, feedback: 'silent'}) as Envelope<Results>
    if (!response.success || !response.data) {error.value = response.message || '搜索失败，请重试。'; return}
    results.value = response.data; searched.value = true
  } catch { error.value = '搜索请求失败，请检查 MP 与 PanSou 的连接后重试。' }
  finally { busy.value = false }
}

async function copy(item: Item) {
  notice.value = ''; error.value = ''
  if (item.password_conflict) return
  try {
    await navigator.clipboard.writeText(`${item.title}\n${item.url}${item.password ? '\n提取码：' + item.password : ''}`)
    notice.value = '分享信息已复制。'; toast?.success(notice.value)
  } catch { notice.value = '浏览器无法自动复制，请展开“分享信息”后手动选择复制。' }
}

onMounted(loadStatus)
</script>

<template>
  <section class="mp-search">
    <header class="mp-heading">
      <div><p class="mp-eyebrow">PAN SOU · 115</p><h2>网盘搜索</h2><p>搜索影视资源，核对分享信息。</p></div>
      <div class="mp-actions"><button type="button" @click="emit('switch')">连接设置</button><button type="button" @click="emit('close')">关闭</button></div>
    </header>
    <div v-if="status && !status.enabled" class="mp-alert" role="status">插件尚未启用，请在连接设置中启用并保存。</div>
    <form class="mp-form" @submit.prevent="search">
      <label>影视名称<input v-model="keyword" name="keyword" maxlength="120" placeholder="例如：无声的回响" :disabled="busy" /></label>
      <label>年份（可选）<input v-model="year" name="year" maxlength="4" inputmode="numeric" placeholder="2026" :disabled="busy" /></label>
      <label>清晰度<select v-model="resolution" name="resolution" :disabled="busy"><option value="all">全部</option><option value="2160p">4K / 2160p</option><option value="1080p">1080p</option></select></label>
      <button class="mp-primary" type="submit" :disabled="busy || !status?.enabled || !!status?.config_error">{{ busy ? '搜索中…' : '搜索资源' }}</button>
    </form>
    <p class="mp-muted">仅搜索 115 · 标题中的季集、画质和链接有效性待自行核实</p>
    <div v-if="error" class="mp-alert mp-error" role="alert">{{ error }} <button v-if="!status" type="button" @click="loadStatus">重新连接</button></div>
    <div v-if="notice" class="mp-alert" role="status">{{ notice }}</div>
    <div v-if="busy" class="mp-empty" role="status">正在从 PanSou 搜索，请稍候…</div>
    <template v-if="results">
      <p class="mp-summary">找到 {{ results.items.length }} 个分享 · 合并 {{ results.duplicates }} 次重复 · 过滤 {{ results.filtered }} 条不匹配</p>
      <p v-if="results.truncated" class="mp-alert">结果较多，仅展示前 200 条。可添加年份或清晰度缩小范围。</p>
      <div class="mp-grid">
        <article v-for="item in results.items" :key="item.id" class="mp-card">
          <span class="mp-tag">115 · {{ item.collection ? '合集' : '分享资源' }}</span>
          <h3>{{ item.title }}</h3>
          <p>{{ item.quality }} · {{ item.episode }}</p>
          <p class="mp-muted">来源：{{ item.source }} <span v-if="item.published"> · {{ item.published }}</span></p>
          <p v-if="item.password_conflict" class="mp-warning">同一分享存在不同提取码，请手动核对，已禁用快捷操作。</p>
          <details><summary>分享信息</summary><p class="mp-share">{{ item.url }}</p><p>提取码：{{ item.password || '未提供' }}</p></details>
          <footer><button type="button" :disabled="item.password_conflict" @click="copy(item)">复制分享</button><a v-if="!item.password_conflict" :href="item.url" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">打开分享 ↗</a></footer>
        </article>
      </div>
    </template>
    <div v-if="searched && !results?.items.length" class="mp-empty">未找到匹配的 115 分享，可调整关键词或筛选条件后重试。</div>
    <div v-if="!searched && !busy && !error" class="mp-empty">输入片名，开始第一次搜索。</div>
  </section>
</template>

<style scoped>
.mp-search{padding:24px;color:rgb(var(--v-theme-on-surface,35,42,56));font-family:inherit}.mp-heading,.mp-actions,.mp-card footer{display:flex;justify-content:space-between;align-items:center;gap:12px}.mp-heading{align-items:flex-start;margin-bottom:24px}.mp-heading h2{font-size:28px;margin:0 0 6px}.mp-heading p{margin:0}.mp-eyebrow{font-size:11px;letter-spacing:2px;opacity:.65;padding-bottom:8px}.mp-form{display:grid;grid-template-columns:minmax(180px,1fr) 120px 150px auto;gap:12px;align-items:end}.mp-form label{font-size:13px;display:grid;gap:7px}.mp-search input,.mp-search select{width:100%;padding:11px 12px;border:1px solid rgba(var(--v-theme-on-surface,35,42,56),.23);border-radius:8px;background:rgb(var(--v-theme-surface,255,255,255));color:inherit;font:inherit}.mp-search button,.mp-search a{font:inherit;font-size:13px;padding:10px 14px;border-radius:8px;border:1px solid rgba(var(--v-theme-on-surface,35,42,56),.2);background:transparent;color:inherit;cursor:pointer;text-decoration:none}.mp-search button:disabled{opacity:.45;cursor:default}.mp-search .mp-primary{background:rgb(var(--v-theme-primary,75,102,225));color:white;border-color:transparent;min-height:43px}.mp-muted{font-size:12px;opacity:.65;overflow-wrap:anywhere}.mp-summary{font-size:13px;margin:24px 0 14px}.mp-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,310px),1fr));gap:16px}.mp-card{padding:20px;border:1px solid rgba(var(--v-theme-on-surface,35,42,56),.15);border-radius:12px;min-width:0;background:rgba(var(--v-theme-surface,255,255,255),.65)}.mp-card h3{font-size:16px;line-height:1.6;overflow-wrap:anywhere}.mp-card p{font-size:13px}.mp-tag{font-size:11px;opacity:.7}.mp-card footer{margin-top:22px;flex-wrap:wrap}.mp-card summary{font-size:13px;cursor:pointer}.mp-share{word-break:break-all;user-select:text}.mp-empty{text-align:center;padding:48px 12px;opacity:.65}.mp-alert{padding:12px 16px;margin:14px 0;background:rgba(80,120,200,.1);border-radius:8px;font-size:13px}.mp-error{background:rgba(200,60,60,.12)}.mp-warning{color:#b7791f}.mp-search input:focus,.mp-search select:focus{outline:2px solid rgb(var(--v-theme-primary,75,102,225));outline-offset:2px}@media(max-width:650px){.mp-search{padding:16px}.mp-form{grid-template-columns:1fr 1fr}.mp-form label:first-child{grid-column:1/-1}.mp-primary{grid-column:1/-1}.mp-heading{flex-wrap:wrap}}
</style>
