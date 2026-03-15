const TOKEN_KEY = "qualify_token"

export function initToken(): void {
  const params = new URLSearchParams(window.location.search)
  const token = params.get("token")
  if (token) {
    sessionStorage.setItem(TOKEN_KEY, token)
    params.delete("token")
    const newUrl = window.location.pathname + (params.toString() ? `?${params}` : "")
    window.history.replaceState({}, "", newUrl)
  }
}

export function getToken(): string {
  return sessionStorage.getItem(TOKEN_KEY) ?? ""
}
