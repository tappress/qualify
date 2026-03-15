import axios from "axios"
import { getToken } from "./auth"

export const api = axios.create({ baseURL: "/api" })

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

/** Returns the SSE URL with ?token= appended (EventSource can't set headers). */
export function sseUrl(path: string): string {
  const token = getToken()
  return token ? `${path}?token=${encodeURIComponent(token)}` : path
}
