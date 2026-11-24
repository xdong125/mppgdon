export function mapLibraryPath(path: string, rules: string): string {
  const normalize = (value: string) => value.trim().replace(/\\/g, '/').replace(/\/+$/, '') || '/'
  const mappings = rules.split('\n').filter(line => line.trim()).map(line => {
    const parts = line.split('#')
    if (parts.length !== 2 || !parts[0].trim() || !parts[1].trim()) throw new Error('路径替换格式应为 MP前缀#CMS前缀，一行一条。')
    const [source, target] = parts.map(normalize)
    if (!/^(\/|[a-zA-Z]:\/)/.test(source) || !target.startsWith('/') || [...source.split('/'), ...target.split('/')].includes('..')) {
      throw new Error('MP 前缀须为绝对路径，CMS 前缀须为 Linux 绝对路径，不能包含 ..。')
    }
    return {source, target}
  }).sort((a, b) => b.source.length - a.source.length)
  const seen = new Set<string>()
  for (const {source} of mappings) {
    if (seen.has(source)) throw new Error('同一 MP 前缀不能设置多个替换目标。')
    seen.add(source)
  }
  const value = normalize(path)
  const rule = mappings.find(({source}) => value === source || value.startsWith(source === '/' ? '/' : source + '/'))
  if (!rule) return value
  const tail = value.slice(rule.source.length).replace(/^\/+/, '')
  return rule.target.replace(/\/+$/, '') + (tail ? '/' + tail : '') || '/'
}
