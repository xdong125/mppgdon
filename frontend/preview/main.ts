import { createApp, h, ref } from 'vue'
import * as Vue from 'vue'
import Page from '../src/Page.vue'
import Config from '../src/Config.vue'
const config = ref({enabled: true, pansou_url: 'https://pansou.tiandechi.com', pansou_token: ''})
const configuring = ref(false)
const api = {
  async get() {return {success: true, message: '', data: {...config.value, version: '0.2.1', token_set: false, config_error: ''}}},
  async post(_path: string, request: {keyword: string}) {return {success: true, message: '', data: {
    keyword: request.keyword, raw_115: 3, duplicates: 1, filtered: 0, truncated: false,
    items: [1,2].map(n => ({id: 'preview'+n, title: `${request.keyword} (2026) S01E0${n} 4K WEB-DL`,
      url: `https://115cdn.com/s/preview${n}`, password: 'demo', source: '演示数据（非真实分享）',
      published: '', quality: '2160p', episode: `S01E0${n}`, collection: false, password_conflict: false})),
  }}}
}
let PageComponent = Page, ConfigComponent = Config
if (location.search.includes('federation')) {
  // 开发宿主提供唯一的 Vue 实例，用真正的构建产物验证联邦入口。
  const remote = await import('../../plugins.v3/mppgdontest/dist/assets/remoteEntry.js')
  await remote.init({vue: {[Vue.version]: {get: () => Promise.resolve(() => Vue), loaded: true, from: 'preview-host', shareConfig: {singleton: true, requiredVersion: false}}}})
  PageComponent = (await remote.get('./Page'))().default
  ConfigComponent = (await remote.get('./Config'))().default
}
createApp({render: () => configuring.value
  ? h(ConfigComponent, {initialConfig: config.value, onSave: (value: typeof config.value) => {config.value = value; configuring.value = false}, onSwitch: () => {configuring.value = false}})
  : h(PageComponent, {api, pluginId: 'MppgdonTest', onSwitch: () => {configuring.value = true}}),
}).mount('#app')
