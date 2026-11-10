// SSE 手动解析：fetch + ReadableStream（EventSource 不支持 POST 带 JSON 体）
export async function streamAsk(question, handlers) {
  const resp = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  if (!resp.ok || !resp.body) throw new Error(`连接失败: HTTP ${resp.status}`)

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

export const getSchema = () =>
  fetch('/api/schema').then((r) => r.json())
