import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Page from '../src/Page.vue'
import Config from '../src/Config.vue'

function setup(post = vi.fn()) {
  const api = {get: vi.fn().mockResolvedValue({success: true, message: '', data: {enabled: true, version: '0.2.0', pansou_url: 'https://example.test', token_set: false, config_error: ''}}), post}
  const wrapper = mount(Page, {props: {api, pluginId: 'MppgdonTestCopy'}})
  return {wrapper, api}
}
const item = {id: 'abc', title: '<img src=x onerror=alert(1)>', url: 'https://115cdn.com/s/example', password: 'abcd', source: 'fixture', published: '', quality: '2160p', episode: 'S01E01', collection: false, password_conflict: false}

describe('search page host contract', () => {
  it('uses scoped API, current instance ID and final envelope; renders text safely', async () => {
    const {wrapper, api} = setup(vi.fn().mockResolvedValue({success: true, message: '', data: {items: [item], duplicates: 1, filtered: 2}}))
    await flushPromises()
    await wrapper.get('input[name=keyword]').setValue('测试剧')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(api.post).toHaveBeenCalledWith('plugin/MppgdonTestCopy/search', {keyword: '测试剧', year: '', resolution: 'all'}, expect.objectContaining({feedback: 'silent', timeout: 65000}))
    expect(wrapper.findAll('article')).toHaveLength(1)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toContain(item.title)
    expect(wrapper.get('a').attributes('rel')).toBe('noopener noreferrer')
  })
  it('does not send empty or invalid year searches', async () => {
    const {wrapper, api} = setup(); await flushPromises()
    await wrapper.get('form').trigger('submit')
    expect(api.post).not.toHaveBeenCalled()
    await wrapper.get('input[name=keyword]').setValue('测试剧')
    await wrapper.get('input[name=year]').setValue('bad')
    await wrapper.get('form').trigger('submit')
    expect(api.post).not.toHaveBeenCalled()
  })
  it('distinguishes business failure from a successful empty result', async () => {
    const {wrapper, api} = setup(vi.fn().mockResolvedValueOnce({success: false, message: 'PanSou HTTP 429', data: null}).mockResolvedValueOnce({success: true, message: '', data: {items: [], duplicates: 0, filtered: 0}}))
    await flushPromises(); await wrapper.get('input[name=keyword]').setValue('测试剧')
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(wrapper.get('[role=alert]').text()).toContain('429')
    expect(wrapper.text()).not.toContain('未找到匹配')
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(wrapper.text()).toContain('未找到匹配')
    expect(api.post).toHaveBeenCalledTimes(2)
  })
  it('prevents double submits and does not retry a network rejection', async () => {
    let reject!: (reason: Error) => void
    const {wrapper, api} = setup(vi.fn().mockImplementation(() => new Promise((_, fail) => {reject = fail})))
    await flushPromises(); await wrapper.get('input[name=keyword]').setValue('测试剧')
    await wrapper.get('form').trigger('submit'); await wrapper.get('form').trigger('submit')
    expect(api.post).toHaveBeenCalledTimes(1)
    reject(new Error('network')); await flushPromises()
    expect(wrapper.get('[role=alert]').text()).toContain('连接')
    expect(wrapper.get('button[type=submit]').attributes('disabled')).toBeUndefined()
  })
  it('blocks quick actions for conflicting passwords and preserves manual details', async () => {
    const {wrapper} = setup(vi.fn().mockResolvedValue({success: true, message: '', data: {items: [{...item, password_conflict: true}], duplicates: 1, filtered: 0}}))
    await flushPromises(); await wrapper.get('input[name=keyword]').setValue('测试剧')
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(wrapper.get('[aria-label="复制分享"]').attributes('disabled')).toBeDefined()
    expect(wrapper.find('article a').exists()).toBe(false)
    const detailsButton = wrapper.get('[aria-label="分享信息"]')
    expect(detailsButton.attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('.mp-details').exists()).toBe(false)
    await detailsButton.trigger('click')
    expect(detailsButton.attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('.mp-details').text()).toContain('abcd')
    await detailsButton.trigger('click')
    expect(wrapper.find('.mp-details').exists()).toBe(false)
  })
  it('reveals duplicate records under their share without reissuing the search', async () => {
    const duplicate = {title: '测试剧 1080p', origin: 'raw', quality: '1080p', source: '其他来源', published: '2026-11-24'}
    const {wrapper, api} = setup(vi.fn().mockResolvedValue({success: true, message: '', data: {
      items: [{...item, duplicate_records: [duplicate]}], duplicates: 2, filtered: 0,
    }}))
    await flushPromises()
    await wrapper.get('input[name=keyword]').setValue('测试剧')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    const toggle = wrapper.get('.mp-duplicates-toggle')
    expect(toggle.text()).toBe('展开重复')
    expect(wrapper.find('.mp-duplicate').exists()).toBe(false)
    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('article .mp-duplicate').text()).toContain('原始结果 · 1080p · 其他来源 · 2026-11-24')
    expect(wrapper.text()).toContain('显示 1 / 2 条重复记录')
    await toggle.trigger('click')
    expect(wrapper.find('.mp-duplicate').exists()).toBe(false)
    expect(api.post).toHaveBeenCalledOnce()
    wrapper.unmount()
  })
})

describe('configuration upgrade', () => {
  it('preserves enabled and unknown legacy config fields when saving', async () => {
    const wrapper = mount(Config, {props: {initialConfig: {enabled: true, message: 'legacy'}}})
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('save')?.[0]?.[0]).toEqual({enabled: true, message: 'legacy', pansou_url: 'https://pansou.tiandechi.com', pansou_token: ''})
  })
  it('rejects URLs containing credentials', async () => {
    const wrapper = mount(Config, {props: {initialConfig: {pansou_url: 'https://user:secret@host'}}})
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('save')).toBeUndefined()
    expect(wrapper.get('[role=alert]').text()).toContain('有效')
  })
})
