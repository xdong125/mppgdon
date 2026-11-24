<script setup lang="ts">
import { ref, watch } from 'vue'
const props = defineProps<{initialConfig?: Record<string, unknown>}>()
const emit = defineEmits(['save', 'close', 'switch'])
const config = ref({enabled: false, pansou_url: 'https://pansou.tiandechi.com', pansou_token: '',
  cms_url: '', cms_login_token: '', cms_sync_path: '', cms_sync_cid: '0', cms_sync_live: false, ...props.initialConfig})
const error = ref('')
watch(() => props.initialConfig, value => {if (value) config.value = {...config.value, ...value}})
function save() {
  error.value = ''
  try {
    const url = new URL(String(config.value.pansou_url))
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error()
  } catch { error.value = '请填写有效的 PanSou HTTP/HTTPS 服务地址。'; return }
  if (config.value.cms_url || config.value.cms_sync_path || config.value.cms_sync_live) {
    try {
      const url = new URL(config.value.cms_url.trim())
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || url.pathname !== '/') throw new Error()
    } catch { error.value = '请填写 CMS 根地址，不带路径、账号或查询参数。'; return }
    const path = config.value.cms_sync_path.trim().replace(/\/+$/, '')
    if (!path.startsWith('/media/') || path.length > 512 || path.includes('\\') || path.slice(1).split('/').some(part => ['', '.', '..'].includes(part))) {
      error.value = '请填写 CMS 容器内 /media/ 下的具体 STRM 目录。'; return
    }
    if (!/^[0-9]{1,20}$/.test(String(config.value.cms_sync_cid).trim())) {
      error.value = '分享目录 CID 必须是数字，0 表示整个分享。'; return
    }
    const token = config.value.cms_login_token.trim().replace(/^(?:Authorization:\s*)?Bearer\s+/i, '')
    if ((config.value.cms_login_token.trim() || config.value.cms_sync_live) && !/^[A-Za-z0-9._~+/=-]{1,8192}$/.test(token)) {
      error.value = '请填写 CMS 网页登录 Bearer Token，不要填写 Cookie。'; return
    }
  }
  emit('save', {...config.value})
}
</script>
<template>
  <section class="mp-config">
    <h2>网盘搜索 · 连接设置</h2>
    <p>配置保存后，进入搜索页输入影视名称即可搜索。</p>
    <form @submit.prevent="save">
      <label class="mp-toggle"><input v-model="config.enabled" type="checkbox" /> 启用网盘搜索</label>
      <label>PanSou 服务地址<input v-model="config.pansou_url" type="url" required placeholder="https://pansou.tiandechi.com" /></label>
      <label>PanSou Token（可选）<input v-model="config.pansou_token" type="password" autocomplete="off" placeholder="公开服务通常留空" /></label>
      <p>这里填写 PanSou 的认证 Token；当前默认公开服务可留空。地址填写服务根地址，搜索请求由 MP 后端发送。</p>
      <fieldset class="cms-settings">
        <legend>CMS 分享同步</legend>
        <label>CMS 根地址<input v-model="config.cms_url" type="url" placeholder="http://NAS地址:端口" /></label>
        <label>CMS 网页登录 Token<input v-model="config.cms_login_token" type="password" autocomplete="new-password" maxlength="8214" placeholder="Bearer Token，不是 Cookie 或 CMS_API_TOKEN" /></label>
        <label>STRM 目录（CMS 容器内）<input v-model="config.cms_sync_path" type="text" maxlength="512" placeholder="/media/网盘影视" /></label>
        <label>分享目录 CID（0 = 整个分享）<input v-model="config.cms_sync_cid" type="text" inputmode="numeric" maxlength="20" /></label>
        <label class="mp-toggle"><input v-model="config.cms_sync_live" type="checkbox" /> 启用真实提交（未勾选时仅演练）</label>
      </fieldset>
      <p v-if="error" role="alert">{{ error }}</p>
      <footer><button type="button" @click="emit('close')">关闭</button><button type="button" @click="emit('switch')">前往搜索</button><button class="mp-save" type="submit">保存配置</button></footer>
    </form>
  </section>
</template>
<style scoped>
.mp-config{padding:24px;color:rgb(var(--v-theme-on-surface,35,42,56));font-family:inherit}.mp-config h2{font-size:22px}.mp-config p{font-size:13px;opacity:.7;line-height:1.7}.mp-config form{display:grid;gap:20px;margin-top:24px}.mp-config label{display:grid;gap:8px;font-size:14px}.mp-config input:not([type=checkbox]){border:1px solid rgba(var(--v-theme-on-surface,35,42,56),.25);border-radius:8px;padding:12px;color:inherit;background:transparent;font:inherit;width:100%}.mp-config .mp-toggle{display:flex;align-items:center}.mp-config footer{display:flex;justify-content:flex-end;gap:12px;flex-wrap:wrap}.mp-config button{padding:10px 16px;border:1px solid rgba(var(--v-theme-on-surface,35,42,56),.2);border-radius:8px;color:inherit;background:transparent;cursor:pointer;font:inherit}.mp-config .mp-save{background:rgb(var(--v-theme-primary,75,102,225));color:white;border:0}
.cms-settings{min-width:0;margin:0;padding:14px;border:1px solid rgba(var(--v-theme-on-surface,35,42,56),.2);border-radius:8px;display:grid;gap:12px}
.cms-settings legend{padding:0 6px;font-size:14px;font-weight:600}
.cms-settings input{box-sizing:border-box;min-width:0}
</style>
