import { createApp, h, ref } from 'vue'
import * as Vue from 'vue'
import AppPage from '../src/AppPage.vue'
import Config from '../src/Config.vue'
const config = ref({enabled: true, pansou_url: 'https://pansou.tiandechi.com', cms_url: 'https://cms.example',
  cms_sync_cid: '0', cms_sync_live: false,
  cms_api_token:'', cms_transfer_live:false,
  library_movie_root: '/mnt/media/电影', library_tv_root: '/mnt/media/电视剧', library_path_mapping: '/mnt/media#/media'})
const configure = ref(location.search.includes('config'))
let scanned = false
const libraryRows = [
  {path:'/mnt/media/电视剧/示例剧', parent:'/mnt/media/电视剧', root:'/mnt/media/电视剧', kind:'tv', entry_type:'directory', title:'示例剧', scraped:true, nfo_path:'/mnt/media/电视剧/示例剧/tvshow.nfo', missing_images:['logo']},
  {path:'/mnt/media/电视剧/示例剧/S01', parent:'/mnt/media/电视剧/示例剧', root:'/mnt/media/电视剧', kind:'tv', entry_type:'directory', title:'S01', scraped:null, missing_images:[]},
  {path:'/mnt/media/电视剧/示例剧/S01/示例剧.S01E01.strm', parent:'/mnt/media/电视剧/示例剧/S01', root:'/mnt/media/电视剧', kind:'tv', entry_type:'media', title:'示例剧 · 第一集', scraped:true, season:'1', episode:'1', nfo_path:'/mnt/media/电视剧/示例剧/S01/示例剧.S01E01.nfo', missing_images:['thumbnail']},
  {path:'/mnt/media/电视剧/示例剧/S01/示例剧.S01E02.strm', parent:'/mnt/media/电视剧/示例剧/S01', root:'/mnt/media/电视剧', kind:'tv', entry_type:'media', title:'示例剧 · 第二集', scraped:false, nfo_state:'missing', season:'1', episode:'2', missing_images:['thumbnail']},
  {path:'/mnt/media/电影/示例电影 (2026)/示例电影.strm', parent:'/mnt/media/电影/示例电影 (2026)', root:'/mnt/media/电影', kind:'movie', entry_type:'media', title:'示例电影', scraped:true, year:'2026', missing_images:[]},
].map(item => ({year:'', season:'', episode:'', tmdb_id:'', nfo_path:'', nfo_state:'valid', present:true,
  checked_at:'2026-11-24T10:00:00Z', ...item, cms_path:item.path.replace('/mnt/media','/media')}))

function libraryView(params: Record<string, unknown> = {}) {
  const rows = scanned ? libraryRows.filter(item => (!params.kind || params.kind === item.kind)
    && (!params.entry_type || params.entry_type === item.entry_type) && (!params.parent || params.parent === item.parent)
    && (!params.keyword || item.path.includes(String(params.keyword)) || item.title.includes(String(params.keyword)))
    && (!params.scrape || params.scrape === 'scraped' && item.scraped || params.scrape === 'not_scraped' && item.scraped === false
      || params.scrape === 'incomplete' && item.scraped && item.missing_images.length)) : []
  return {roots:[{kind:'movie', mp_path:config.value.library_movie_root, cms_path:'/media/电影'}, {kind:'tv', mp_path:config.value.library_tv_root, cms_path:'/media/电视剧'}],
    summary:scanned ? {directories:2, media:3, strm:3, scraped:2, not_scraped:1, incomplete:1, shows:1, shows_scraped:1} : {},
    scan:{status:scanned ? 'complete' : 'idle', entries:scanned ? 12 : 0, parsed_nfo:3, reused_nfo:0, skipped_links:0, errors:[], finished_at:scanned ? '2026-11-24T10:00:00Z' : ''},
    items:rows, total:rows.length, page:1, config_error:''}
}
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
  async get(path: string, options?: {params?: Record<string, unknown>}) {
    const params = options?.params
    if (path.endsWith('/library')) return {success:true, message:'', data:libraryView(params)}
    const data = path === 'media/search' ? [...movies, ...shows].filter(item => String(item.title).includes(String(params?.title ?? '')))
      : path.startsWith('discover/') ? (path.endsWith('_tvs') ? shows : movies).filter(item => Number(item.vote_average) >= Number(params?.vote_average ?? 0))
      : {enabled: config.value.enabled, pansou_url: config.value.pansou_url, token_set: false,
          config_error: '', sync_mode: config.value.cms_sync_live ? 'live' : 'dry_run',
          transfer_mode:config.value.cms_transfer_live ? 'live' : 'dry_run', version: '0.7.0'}
    return {success: true, message: '', data}
  },
  async post(path: string, request: {keyword: string; year?: string; media_type?: string; season?: number}) {
    if (path.endsWith('/library/scan')) {scanned = true; return {success:true, message:'模拟扫描完成。', data:libraryView()}}
    if (path.endsWith('/transfer')) return {success:true, message:'模拟转存完成，未请求任何 CMS。', data:{status:'dry_run', retryable:false, attempt_id:null}}
    if (path.endsWith('/share-sync')) return {success: true, message: '模拟提交完成，未请求任何 CMS。', data: {status: 'dry_run'}}
    return {success: true, message: '', data: {
    keyword: request.keyword, raw_115: 3, duplicates: 1, filtered: 0, truncated: false,
    items: [1,2].map(n => ({id: 'preview'+n, title: `${request.keyword} ${request.year ? `(${request.year}) ` : ''}4K WEB-DL · 样例 ${n}`,
      url: `https://115cdn.com/s/preview${n}`, password: 'demo', source: '演示数据（非真实分享）',
      published: '', quality: '2160p', episode: '季集未标注', collection: false, password_conflict: false, sync_ticket: `preview-ticket-${n}`,
      transfer_ticket:`preview-transfer-ticket-${n}`,
      sync_target: {mp_path:`/mnt/media/${request.media_type === 'tv' ? `电视剧/${request.keyword}/S${String(request.season ?? 1).padStart(2,'0')}` : `电影/${request.keyword} (${request.year || '2026'})`}`,
        cms_path:`/media/${request.media_type === 'tv' ? `电视剧/${request.keyword}/S${String(request.season ?? 1).padStart(2,'0')}` : `电影/${request.keyword} (${request.year || '2026'})`}`, kind:request.media_type || 'movie', season:request.season ?? null, reason:'演示目标'},
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
