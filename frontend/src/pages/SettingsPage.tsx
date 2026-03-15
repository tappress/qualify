import { useState, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { api } from "@/lib/api"
import type { AppSettings, Server } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { CheckCircle, KeyRound } from "lucide-react"

export default function SettingsPage() {
  const qc = useQueryClient()

  const { data: settings, isLoading } = useQuery<AppSettings>({
    queryKey: ["settings"],
    queryFn: () => api.get("/settings/").then((r) => r.data),
  })

  const { data: servers } = useQuery<Server[]>({
    queryKey: ["servers"],
    queryFn: () => api.get("/servers/").then((r) => r.data),
  })

  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.put("/settings/", body).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] })
      toast.success("Settings saved")
    },
    onError: () => toast.error("Failed to save settings"),
  })

  // Cloudflare form
  const [cfToken, setCfToken] = useState("")
  const [cfZoneId, setCfZoneId] = useState("")

  // Registry form
  const [regUrl, setRegUrl] = useState("")
  const [regUser, setRegUser] = useState("")

  // Primary server
  const [primaryServer, setPrimaryServer] = useState("")

  useEffect(() => {
    if (!settings) return
    setCfZoneId(settings.cloudflare_zone_id)
    setRegUrl(settings.registry.url)
    setRegUser(settings.registry.username)
    setPrimaryServer(settings.primary_server_id ?? "")
  }, [settings])

  if (isLoading) return <div className="p-6"><Skeleton className="h-64 w-full" /></div>

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold">Settings</h1>

      {/* Cloudflare */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Cloudflare DNS (optional)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            {settings?.cloudflare_token_stored ? (
              <><CheckCircle size={14} className="text-green-600" /> API token stored in OS keyring</>
            ) : (
              <><KeyRound size={14} /> No token stored</>
            )}
          </div>
          <div>
            <Label>API Token {settings?.cloudflare_token_stored && <span className="text-muted-foreground text-xs">(leave blank to keep existing)</span>}</Label>
            <Input
              type="password"
              placeholder={settings?.cloudflare_token_stored ? "••••••••" : "Cloudflare API token"}
              value={cfToken}
              onChange={(e) => setCfToken(e.target.value)}
            />
          </div>
          <div>
            <Label>Zone ID</Label>
            <Input
              placeholder="abc123..."
              value={cfZoneId}
              onChange={(e) => setCfZoneId(e.target.value)}
            />
          </div>
          <Button
            size="sm"
            disabled={save.isPending}
            onClick={() =>
              save.mutate({
                cloudflare_zone_id: cfZoneId,
                ...(cfToken ? { cloudflare_token: cfToken } : {}),
              })
            }
          >
            Save Cloudflare
          </Button>
        </CardContent>
      </Card>

      {/* Docker Registry */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Docker Registry</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-muted-foreground">
            Qualify provisions a private registry on your server automatically. These settings are for a custom external registry.
          </p>
          <div>
            <Label>Registry URL</Label>
            <Input
              placeholder="registry.myapp.com"
              value={regUrl}
              onChange={(e) => setRegUrl(e.target.value)}
            />
          </div>
          <div>
            <Label>Username</Label>
            <Input
              placeholder="myuser"
              value={regUser}
              onChange={(e) => setRegUser(e.target.value)}
            />
          </div>
          <Button
            size="sm"
            disabled={save.isPending}
            onClick={() => save.mutate({ registry: { url: regUrl, username: regUser } })}
          >
            Save Registry
          </Button>
        </CardContent>
      </Card>

      {/* Primary server */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Primary Server</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-muted-foreground">
            Used as the default server when creating environments.
          </p>
          <select
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs focus:outline-none focus:ring-1 focus:ring-ring"
            value={primaryServer}
            onChange={(e) => setPrimaryServer(e.target.value)}
          >
            <option value="">— None —</option>
            {servers?.map((s) => (
              <option key={s.id} value={s.id}>{s.name} ({s.host})</option>
            ))}
          </select>
          <Button
            size="sm"
            disabled={save.isPending}
            onClick={() => save.mutate({ primary_server_id: primaryServer || null })}
          >
            Save
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
