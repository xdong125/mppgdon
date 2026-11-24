import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import AppPage from '../src/AppPage.vue'

const movie = { tmdb_id: 12, type: '电影', title: '野兽之心', year: '2026', poster_path: null, vote_average: 7.9 }
const status = { enabled: true, config_error: '' }
const ok = (data: unknown) => ({ success: true, message: '', data })

describe('TheMovieDb 全页入口', () => {
  it('按媒体类型、排序、风格、语言和评分使用宿主发现接口', async () => {
    const get = vi.fn().mockResolvedValue(ok([movie]))
    const wrapper = mount(AppPage, { props: { api: { get, post: vi.fn() }, pluginId: 'MppgdonTest' } })
    await flushPromises()
    expect(get).toHaveBeenLastCalledWith('discover/tmdb_movies', expect.objectContaining({ params: expect.objectContaining({ page: 1 }) }))
    const press = (label: string) => wrapper.findAll('button').find(button => button.text() === label)!.trigger('click')
    await press('电视剧')
    await press('首播日期降序')
    await press('动作冒险')
    await press('日语')
    await wrapper.get('input[type=range]').setValue('7.5')
    await flushPromises()
    expect(get).toHaveBeenLastCalledWith('discover/tmdb_tvs', expect.objectContaining({ params: {
      sort_by: 'first_air_date.desc', with_genres: '10759', with_original_language: 'ja', vote_average: 7.5, vote_count: 10, page: 1,
    } }))
    wrapper.unmount()
  })

  it('通过 TheMovieDb 查询片名，并将海报的片名与年份带入当前实例的 115 搜索', async () => {
    const showModal = vi.fn()
    const original = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'showModal')
    Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: showModal })
    const get = vi.fn().mockImplementation(async (path: string) => path.endsWith('/status') ? ok(status) : ok([movie]))
    const post = vi.fn().mockResolvedValue(ok({ items: [], duplicates: 0, filtered: 0 }))
    const wrapper = mount(AppPage, { props: { api: { get, post }, pluginId: 'MppgdonTestCopy' } })
    try {
      await wrapper.get('input[type=search]').setValue('野兽之心')
      await wrapper.get('.title-search').trigger('submit')
      await flushPromises()
      expect(get).toHaveBeenLastCalledWith('media/search', expect.objectContaining({ params: {
        title: '野兽之心', type: 'media', media_source: 'themoviedb', page: 1, count: 20,
      } }))
      expect(post).not.toHaveBeenCalled()
      await wrapper.get('.poster-card').trigger('click')
      await flushPromises()
      expect(showModal).toHaveBeenCalledOnce()
      expect(post).toHaveBeenCalledExactlyOnceWith('plugin/MppgdonTestCopy/search', {
        keyword: '野兽之心', year: '2026', resolution: 'all',
      }, expect.objectContaining({ feedback: 'silent' }))
      await wrapper.get('dialog').trigger('close')
      expect(wrapper.find('.poster-card').exists()).toBe(true)
      expect(wrapper.find('dialog .mp-search').exists()).toBe(false)
    } finally {
      wrapper.unmount()
      if (original) Object.defineProperty(HTMLDialogElement.prototype, 'showModal', original)
      else Reflect.deleteProperty(HTMLDialogElement.prototype, 'showModal')
    }
  })
})
