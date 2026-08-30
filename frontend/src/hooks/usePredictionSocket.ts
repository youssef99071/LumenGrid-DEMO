import { useEffect, useRef, useState } from 'react'
import { type WsMessage, wsUrl } from '../api'

export function usePredictionSocket(onMessage: (msg: WsMessage) => void) {
  const [connected, setConnected] = useState(false)
  const handler = useRef(onMessage)
  handler.current = onMessage

  useEffect(() => {
    let ws: WebSocket | null = null
    let closed = false
    let retry: number | undefined

    const connect = () => {
      if (closed) return
      ws = new WebSocket(wsUrl())
      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        if (!closed) retry = window.setTimeout(connect, 2000)
      }
      ws.onerror = () => ws?.close()
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string) as WsMessage
          handler.current(data)
        } catch {
          /* ignore malformed */
        }
      }
    }

    connect()
    return () => {
      closed = true
      if (retry) window.clearTimeout(retry)
      ws?.close()
    }
  }, [])

  return connected
}
