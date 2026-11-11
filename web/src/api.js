// SSE 手动解析：fetch + ReadableStream（EventSource 不支持 POST 带 JSON 体）

const TOKEN_KEY = 'askdata_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY) || ''

const authHeaders = () => {
  const t = getToken()
  return t ? { Authorization: `Bearer ${t}` } : {}
}

function on401() {
  localStorage.removeItem(TOKEN_KEY)
  window.dispatchEvent(new Event('askdata:unauthorized'))
}

export async function login(password) {
  const resp = await fetch('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  })
  if (!resp.ok) {
    const e = await resp.json().catch(() => ({}))
    throw new Error(e.detail || `登录失败: HTTP ${resp.status}`)
  }
  const { token } = await resp.json()
  localStorage.setItem(TOKEN_KEY, token)
  return token
}

export async function streamAsk(question, handlers) {
  const resp = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ question }),
  })
  if (!resp.ok || !resp.body) {
    if (resp.status === 401) on401()
    const e = await resp.json().catch(() => ({}))
    throw new Error(e.detail || `连接失败: HTTP ${resp.status}`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const block = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      let event = 'message'
      let data = ''
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data += line.slice(5).trim()
      }
      if (!data) continue
      try {
        handlers[event]?.(JSON.parse(data))
      } catch {
        // 单条坏事件不中断整轮
      }
    }
  }
}

export const getSchema = async () => {
  const resp = await fetch('/api/schema', { headers: authHeaders() })
  if (resp.status === 401) {
    on401()
    throw new Error('未登录')
  }
  return resp.json()
}
