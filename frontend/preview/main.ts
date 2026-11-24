import { createApp, h, ref } from 'vue'
import * as Vue from 'vue'
import AppPage from '../src/AppPage.vue'
import Config from '../src/Config.vue'
const config = ref({enabled: true, pansou_url: 'https://pansou.tiandechi.com', cms_url: 'https://cms.example',
  cms_sync_path: '/media/演示影视', cms_sync_cid: '0', cms_sync_live: false})
const configure = ref(location.search.includes('config'))
const movies = [
  [1726, '钢铁侠', '2008', 7.7, '/78lPtwv72eTNqFW9COBYI0dWDJa.jpg'],
  [157336, '星际穿越', '2014', 8.5, '/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg'],
  [155, '蝙蝠侠：黑暗骑士', '2008', 8.5, '/qJ2tW6WMUDux911r6m7haRef0WH.jpg'],
  [27205, '盗梦空间', '2010', 8.4, '/edv5CZvWj09upOsy2Y6IwDhK8bt.jpg'],
  [438631, '沙丘', '2021', 7.8, '/d5NXSklXo0qyIYkgV94XAgMIckC.jpg'],
  [11, '星球大战', '1977', 8.2, '/6FfCtAuVAW8XJjZ7eWeLibRLWTw.jpg'],
  [603, '黑客帝国', '1999', 8.2, '/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg'],
].map(([tmdb_id, title, year, vote_average, poster_path]) => ({tmdb_id, title, year, vote_average, poster_path, type: '电影'}))
const shows = [{tmdb_id: 66732, title: '怪奇物语', year: '2016', vote_average: 8.6,
  poster_path: '/uOOtwVbSr4QDjAGIifLDwpb2Pdl.jpg', type: '电视剧'}]
const api = {
  async get(path: string, options?: {params?: {title?: string; vote_average?: number}}) {
    const params = options?.params
    const data = path === 'media/search' ? [...movies, ...shows].filter(item => String(item.title).includes(params?.title ?? ''))
      : path.startsWith('discover/') ? (path.endsWith('_tvs') ? shows : movies).filter(item => Number(item.vote_average) >= (params?.vote_average ?? 0))
      : {enabled: config.value.enabled, pansou_url: config.value.pansou_url, token_set: false,
          config_error: '', sync_mode: config.value.cms_sync_live ? 'live' : 'dry_run', version: '0.4.0'}
    return {success: true, message: '', data}
  },
  async post(path: string, request: {keyword: string; year?: string}) {
    if (path.endsWith('/share-sync')) return {success: true, message: '模拟提交完成，未请求任何 CMS。', data: {status: 'dry_run'}}
    return {success: true, message: '', data: {
    keyword: request.keyword, raw_115: 3, duplicates: 1, filtered: 0, truncated: false,
    items: [1,2].map(n => ({id: 'preview'+n, title: `${request.keyword} ${request.year ? `(${request.year}) ` : ''}4K WEB-DL · 样例 ${n}`,
      url: `https://115cdn.com/s/preview${n}`, password: 'demo', source: '演示数据（非真实分享）',
      published: '', quality: '2160p', episode: '季集未标注', collection: false, password_conflict: false, sync_ticket: `preview-ticket-${n}`,
      duplicate_records: n === 1 ? [{title: `${request.keyword} 4K · 重复来源样例`, source: '演示频道',
        published: '2026-11-24T02:00:00Z', quality: '2160p', origin: 'raw'}] : []})),
  }}}
}
let PageComponent = AppPage, ConfigComponent = Config
if (location.search.includes('federation')) {
  // 开发宿主提供唯一的 Vue 实例，用真正的构建产物验证联邦入口。
  const remote = await import('../../plugins.v3/mppgdontest/dist/assets/remoteEntry.js')
  await remote.init({vue: {[Vue.version]: {get: () => Promise.resolve(() => Vue), loaded: true, from: 'preview-host', shareConfig: {singleton: true, requiredVersion: false}}}})
  PageComponent = (await remote.get('./AppPage'))().default
  ConfigComponent = (await remote.get('./Config'))().default
}
createApp({render: () => configure.value
  ? h(ConfigComponent, {initialConfig: config.value, onSave: (value: typeof config.value) => {config.value = value; configure.value = false}, onSwitch: () => {configure.value = false}})
  : h(PageComponent, {api, pluginId: 'MppgdonTest'})}).mount('#app')
