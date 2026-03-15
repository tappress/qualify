import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { api } from "@/lib/api"
import type { Server } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { Plus, ChevronRight, Server as ServerIcon } from "lucide-react"

// ── Status badge ──────────────────────────────────────────────────────────────

const SERVER_STATUS: Record<
  Server["status"],
  { dot: string; text: string; bg: string; label: string }
> = {
  qualified:        { dot: "bg-emerald-500", text: "text-emerald-400", bg: "bg-emerald-500/10", label: "qualified" },
  failed:           { dot: "bg-red-500",     text: "text-red-400",     bg: "bg-red-500/10",     label: "failed" },
  bootstrap_failed: { dot: "bg-red-500",     text: "text-red-400",     bg: "bg-red-500/10",     label: "bootstrap failed" },
  qualifying:       { dot: "bg-blue-400 animate-pulse", text: "text-blue-400", bg: "bg-blue-500/10", label: "qualifying" },
  bootstrapping:    { dot: "bg-blue-400 animate-pulse", text: "text-blue-400", bg: "bg-blue-500/10", label: "bootstrapping" },
  unknown:          { dot: "bg-zinc-500",    text: "text-zinc-400",    bg: "bg-zinc-500/10",    label: "unknown" },
}

function ServerStatusBadge({ status }: { status: Server["status"] }) {
  const s = SERVER_STATUS[status] ?? SERVER_STATUS.unknown
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium ${s.bg} ${s.text}`}>
      <span className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${s.dot}`} />
      {s.label}
    </span>
  )
}

// ── Form defaults ─────────────────────────────────────────────────────────────

const defaultForm = {
  name: "", host: "", port: "22", user: "root",
  ssh_key_path: "~/.ssh/id_rsa", sudo_password: "", tags: "",
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ServersPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(defaultForm)

  const { data: servers, isLoading } = useQuery<Server[]>({
    queryKey: ["servers"],
    queryFn: () => api.get("/servers/").then((r) => r.data),
  })

  const add = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post("/servers/", body).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["servers"] })
      setOpen(false)
      setForm(defaultForm)
      toast.success("Server added")
    },
    onError: () => toast.error("Failed to add server"),
  })

  function handleSubmit(e: React.SyntheticEvent) {
    e.preventDefault()
    add.mutate({
      name: form.name,
      host: form.host,
      port: parseInt(form.port) || 22,
      user: form.user,
      ssh_key_path: form.ssh_key_path,
      sudo_password: form.sudo_password || undefined,
      tags: form.tags ? form.tags.split(",").map((t) => t.trim()).filter(Boolean) : [],
    })
  }

  function field(key: keyof typeof defaultForm) {
    return {
      value: form[key],
      onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
        setForm((f) => ({ ...f, [key]: e.target.value })),
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Servers</h1>
          <p className="text-sm text-muted-foreground mt-0.5">SSH execution targets</p>
        </div>
        <Button onClick={() => setOpen(true)} className="h-9 gap-2">
          <Plus size={15} />
          Add Server
        </Button>
      </div>

      {/* Server list */}
      {isLoading ? (
        <div className="space-y-px rounded-lg overflow-hidden border border-border">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-[68px] w-full rounded-none bg-card" />
          ))}
        </div>
      ) : !servers?.length ? (
        <div className="border border-dashed border-border rounded-lg py-16 text-center">
          <ServerIcon size={24} className="text-muted-foreground/30 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground mb-4">No servers configured yet.</p>
          <Button onClick={() => setOpen(true)} className="h-9 gap-2">
            <Plus size={15} />
            Add your first server
          </Button>
        </div>
      ) : (
        <div className="border border-border rounded-lg overflow-hidden">
          {servers.map((s, i) => (
            <div
              key={s.id}
              className={`flex items-center justify-between px-4 py-4 bg-card hover:bg-muted/30 cursor-pointer transition-colors ${i > 0 ? "border-t border-border" : ""}`}
              onClick={() => navigate(`/servers/${s.id}`)}
            >
              {/* Left: name + connection string */}
              <div className="flex items-center gap-3 min-w-0">
                <div className="p-2 rounded-md bg-muted/60 shrink-0">
                  <ServerIcon size={15} className="text-muted-foreground" strokeWidth={1.5} />
                </div>
                <div className="min-w-0">
                  <p className="font-medium text-sm leading-tight">{s.name}</p>
                  <p className="text-xs text-muted-foreground font-mono mt-0.5 truncate">
                    {s.user}@{s.host}:{s.port}
                  </p>
                </div>
              </div>

              {/* Right: tags + status + chevron */}
              <div className="flex items-center gap-2 shrink-0">
                {s.tags.map((t) => (
                  <span
                    key={t}
                    className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded font-mono"
                  >
                    {t}
                  </span>
                ))}
                {s.status !== "unknown" && <ServerStatusBadge status={s.status} />}
                <ChevronRight size={14} className="text-muted-foreground/30 ml-1" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Server dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md bg-card border-border">
          <DialogHeader>
            <DialogTitle className="text-base">Add Server</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4 mt-1">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground uppercase tracking-wider">Name</Label>
                <Input placeholder="my-vps" required {...field("name")} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground uppercase tracking-wider">Host / IP</Label>
                <Input placeholder="1.2.3.4" required {...field("host")} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground uppercase tracking-wider">SSH Port</Label>
                <Input type="number" {...field("port")} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground uppercase tracking-wider">SSH User</Label>
                <Input {...field("user")} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground uppercase tracking-wider">
                SSH Key Path{" "}
                <span className="normal-case text-muted-foreground/60">(optional)</span>
              </Label>
              <Input className="font-mono text-xs" {...field("ssh_key_path")} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground uppercase tracking-wider">
                Sudo Password{" "}
                <span className="normal-case text-muted-foreground/60">(stored in OS keyring)</span>
              </Label>
              <Input type="password" placeholder="optional" {...field("sudo_password")} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground uppercase tracking-wider">
                Tags{" "}
                <span className="normal-case text-muted-foreground/60">(comma-separated)</span>
              </Label>
              <Input placeholder="prod, web" {...field("tags")} />
            </div>
            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="outline" className="h-9" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" className="h-9" disabled={add.isPending}>
                {add.isPending ? "Adding…" : "Add Server"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
