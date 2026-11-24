<script setup lang="ts">
import { ref, watch } from 'vue'
const props = defineProps<{initialConfig?: Record<string, unknown>}>()
const emit = defineEmits(['save', 'close', 'switch'])
const config = ref({enabled: false, pansou_url: 'https://pansou.tiandechi.com', pansou_token: '', ...props.initialConfig})
const error = ref('')
watch(() => props.initialConfig, value => {if (value) config.value = {...config.value, ...value}})
function save() {
  error.value = ''
  try {
    const url = new URL(String(config.value.pansou_url))
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error()
  } catch { error.value = '请填写有效的 PanSou HTTP/HTTPS 服务地址。'; return }
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
      <p v-if="error" role="alert">{{ error }}</p>
      <footer><button type="button" @click="emit('close')">关闭</button><button type="button" @click="emit('switch')">前往搜索</button><button class="mp-save" type="submit">保存配置</button></footer>
    </form>
  </section>
</template>
<style scoped>
.mp-config{padding:24px;color:rgb(var(--v-theme-on-surface,35,42,56));font-family:inherit}.mp-config h2{font-size:22px}.mp-config p{font-size:13px;opacity:.7;line-height:1.7}.mp-config form{display:grid;gap:20px;margin-top:24px}.mp-config label{display:grid;gap:8px;font-size:14px}.mp-config input:not([type=checkbox]){border:1px solid rgba(var(--v-theme-on-surface,35,42,56),.25);border-radius:8px;padding:12px;color:inherit;background:transparent;font:inherit;width:100%}.mp-config .mp-toggle{display:flex;align-items:center}.mp-config footer{display:flex;justify-content:flex-end;gap:12px;flex-wrap:wrap}.mp-config button{padding:10px 16px;border:1px solid rgba(var(--v-theme-on-surface,35,42,56),.2);border-radius:8px;color:inherit;background:transparent;cursor:pointer;font:inherit}.mp-config .mp-save{background:rgb(var(--v-theme-primary,75,102,225));color:white;border:0}
</style>
