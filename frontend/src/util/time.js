// 时区工具：日志时间一律按「事件所属服务的时区」渲染。
// 后端存 UTC、返回 ISO8601（带偏移或 Z），这里用 Intl.DateTimeFormat 转换。

const dtfCache = new Map()

function formatter(tz, withMs = false) {
  const key = `${tz}|${withMs}`
  if (!dtfCache.has(key)) {
    dtfCache.set(key, new Intl.DateTimeFormat('zh-CN', {
      timeZone: tz,
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: false,
      ...(withMs ? { fractionalSecondDigits: 3 } : {}),
    }))
  }
  return dtfCache.get(key)
}

function parts(dtf, date) {
  const p = {}
  for (const { type, value } of dtf.formatToParts(date)) p[type] = value
  return p
}

export function formatInTz(iso, tz, withMs = true) {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  const p = parts(formatter(tz || 'UTC', withMs), date)
  const ms = withMs && p.fractionalSecond ? `.${p.fractionalSecond}` : ''
  const hour = p.hour === '24' ? '00' : p.hour
  return `${p.year}-${p.month}-${p.day} ${hour}:${p.minute}:${p.second}${ms}`
}

export function formatRelative(iso) {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  const s = Math.round(diff / 1000)
  if (s < 5) return '刚刚'
  if (s < 60) return `${s} 秒前`
  const m = Math.round(s / 60)
  if (m < 60) return `${m} 分钟前`
  const h = Math.round(m / 60)
  if (h < 24) return `${h} 小时前`
  return `${Math.round(h / 24)} 天前`
}

// 求 date 这一时刻，时区 tz 相对 UTC 超前多少分钟（北京 +480，伦敦夏令 +60）。
function offsetMinutes(date, tz) {
  const p = parts(formatter(tz, false), date)
  const hour = p.hour === '24' ? 0 : +p.hour
  const asUtc = Date.UTC(+p.year, +p.month - 1, +p.day, hour, +p.minute, +p.second)
  return Math.round((asUtc - date.getTime()) / 60000)
}

// 把 <input type=datetime-local> 的「墙上时间字符串」按选定 tz 解释为 ISO(UTC)。
// 墙上时间 = UTC + 偏移，故 UTC = 墙上时间 - 偏移（在该时刻附近偏移恒定，夏令时边界误差≤1h 可接受）。
export function localInputToIso(localStr, tz) {
  if (!localStr) return null
  const m = localStr.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?/)
  if (!m) return null
  const [, y, mo, d, h, mi, se] = m
  const wallMs = Date.UTC(+y, +mo - 1, +d, +h, +mi, +(se || 0))
  const offMin = offsetMinutes(new Date(wallMs), tz || 'UTC')
  return new Date(wallMs - offMin * 60000).toISOString()
}

export function toLocalInput(date, tz) {
  const p = parts(formatter(tz || 'UTC', false), date)
  const hour = p.hour === '24' ? '00' : p.hour
  return `${p.year}-${p.month}-${p.day}T${hour}:${p.minute}:${p.second}`
}

export function nowLocalInput(tz) {
  return toLocalInput(new Date(), tz)
}

export function todayStartLocalInput(tz) {
  const p = parts(formatter(tz || 'UTC', false), new Date())
  return `${p.year}-${p.month}-${p.day}T00:00:00`
}

export function shiftLocalInput(localStr, tz, ms) {
  const iso = localInputToIso(localStr, tz)
  if (!iso) return localStr
  return toLocalInput(new Date(new Date(iso).getTime() + ms), tz)
}

export const TZ_LABEL = {
  'Asia/Shanghai': 'UTC+8 北京/上海',
  'Europe/London': 'UTC+0/+1 伦敦',
  UTC: 'UTC',
}
