// 后端全部同源走 /api（开发态由 vite 代理，容器内由前端 nginx 反代）。

async function request(path, params) {
  let url = `/api${path}`
  if (params) {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null || v === '') continue
      qs.append(k, v)
    }
    const s = qs.toString()
    if (s) url += `?${s}`
  }
  const resp = await fetch(url, { headers: { Accept: 'application/json' } })
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    const err = new Error(data.detail || `请求失败 ${resp.status}`)
    err.status = resp.status
    err.data = data
    throw err
  }
  return data
}

export const getMeta = () => request('/meta')
export const getDashboard = () => request('/dashboard')
export const searchLogs = (params) => request('/logs/search', params)
export const getHealth = () => request('/health')
