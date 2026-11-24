import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import Library from '../src/Library.vue'
import Config from '../src/Config.vue'
import { mapLibraryPath } from '../src/libraryPaths'

const row = {path:'/mnt/media/电视剧/示例/S01/E01.strm', parent:'/mnt/media/电视剧/示例/S01', root:'/mnt/media/电视剧',
  kind:'tv', entry_type:'media', title:'第一集', year:'2026', tmdb_id:'', season:'1', episode:'1', scraped:true,
  nfo_state:'valid', nfo_path:'/mnt/media/电视剧/示例/S01/E01.nfo', missing_images:['thumbnail'],
  cms_path:'/media/电视剧/示例/S01/E01.strm', present:true, checked_at:'2026-11-24T08:00:00Z'}
const view = {roots:[{kind:'tv', mp_path:'/mnt/media/电视剧', cms_path:'/media/电视剧'}], summary:{media:1, scraped:1, incomplete:1},
  scan:{status:'complete', entries:4, parsed_nfo:1, reused_nfo:0, skipped_links:0, errors:[], finished_at:''},
  items:[row], total:1, page:1, config_error:''}
const ok = (data: unknown) => ({success:true, data, message:''})

describe('媒体库索引', () => {
  it('显示已刮削但缺图，按目录查询，扫描只在用户点击后发起', async () => {
    const get = vi.fn().mockResolvedValue(ok(view)), post = vi.fn().mockResolvedValue(ok(view))
    const wrapper = mount(Library, {props:{api:{get,post}, pluginId:'MppgdonTestCopy'}})
    await flushPromises()
    expect(post).not.toHaveBeenCalled()
    expect(wrapper.get('.library-badge').text()).toBe('已刮削 · 图片有缺失')
    await wrapper.get('.library-row button').trigger('click')
    expect(wrapper.get('.library-details').text()).toContain('/media/电视剧/示例/S01/E01.strm')
    expect(wrapper.get('.library-details').text()).toContain('单集缩略图')
    await wrapper.get('.library-roots button').trigger('click')
    await flushPromises()
    expect(get).toHaveBeenLastCalledWith('plugin/MppgdonTestCopy/library', expect.objectContaining({params:expect.objectContaining({parent:'/mnt/media/电视剧', entry_type:''})}))
    await wrapper.get('.library-buttons button').trigger('click')
    await flushPromises()
    expect(post).toHaveBeenCalledExactlyOnceWith('plugin/MppgdonTestCopy/library/scan', {}, expect.anything())
    wrapper.unmount()
  })

  it('前缀替换按目录边界匹配，配置预览不提交 CMS', async () => {
    const rules='/mnt/media#/media\n/mnt/media/电视剧#/media/shows'
    expect(mapLibraryPath('/mnt/media/电视剧/示例/S01', rules)).toBe('/media/shows/示例/S01')
    expect(mapLibraryPath('/mnt/media-old/test', rules)).toBe('/mnt/media-old/test')
    const wrapper = mount(Config, {props:{initialConfig:{library_path_mapping:rules, library_tv_root:'/mnt/media/电视剧'}}})
    await wrapper.get('input[placeholder="输入 MP 中的完整路径"]').setValue('/mnt/media/电视剧/示例/S01')
    expect(wrapper.get('output').text()).toBe('/media/shows/示例/S01')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('save')?.[0]?.[0]).toMatchObject({library_path_mapping:rules, library_tv_root:'/mnt/media/电视剧', cms_sync_live:false})
  })
})
