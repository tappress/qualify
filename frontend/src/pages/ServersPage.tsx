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
import { Plus, ChevronRight } from "lucide-react"

function ServerStatusBadge({ status }: { status: Server["status"] }) {
  const styles: Record<string, string> = {
    qualified: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
    qualifying: "bg-blue-100 text-blue-800",
    unknown: "bg-gray-100 text-gray-600",
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[status]}`}>
      {status}
    </span>
  )
}

const defaultForm = {
  name: "", host: "", port: "22", user: "root",
  ssh_key_path: "~/.ssh/id_rsa", sudo_password: "", tags: "",
}

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

  function handleSubmit(e: React.FormEvent) {
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
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold">Servers</h1>
        <Button size="sm" onClick={() => setOpen(true)}>
          <Plus size={16} className="mr-1" /> Add Server
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}
        </div>
      ) : !servers?.length ? (
        <div className="text-center py-16 text-muted-foreground">
          <p className="mb-2">No servers yet.</p>
          <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
            Add your first server
          </Button>
        </div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          {servers.map((s, i) => (
            <div
              key={s.id}
              className={`flex items-center justify-between px-4 py-3 hover:bg-muted/30 cursor-pointer ${i > 0 ? "border-t" : ""}`}
              onClick={() => navigate(`/servers/${s.id}`)}
            >
              <div>
                <p className="font-medium">{s.name}</p>
                <p className="text-sm text-muted-foreground">{s.user}@{s.host}:{s.port}</p>
              </div>
              <div className="flex items-center gap-3">
                <ServerStatusBadge status={s.status} />
                {s.tags.map((t) => (
                  <span key={t} className="text-xs bg-secondary text-secondary-foreground px-1.5 py-0.5 rounded">
                    {t}
                  </span>
                ))}
                <ChevronRight size={16} className="text-muted-foreground" />
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add Server</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-3 mt-2">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Name</Label>
                <Input placeholder="my-vps" required {...field("name")} />
              </div>
              <div>
                <Label>Host / IP</Label>
                <Input placeholder="1.2.3.4" required {...field("host")} />
              </div>
              <div>
                <Label>SSH Port</Label>
                <Input type="number" {...field("port")} />
              </div>
              <div>
                <Label>SSH User</Label>
                <Input {...field("user")} />
              </div>
            </div>
            <div>
              <Label>SSH Key Path <span className="text-muted-foreground text-xs">(optional)</span></Label>
              <Input {...field("ssh_key_path")} />
            </div>
            <div>
              <Label>Sudo Password <span className="text-muted-foreground text-xs">(stored in OS keyring)</span></Label>
              <Input type="password" placeholder="optional" {...field("sudo_password")} />
            </div>
            <div>
              <Label>Tags <span className="text-muted-foreground text-xs">(comma-separated)</span></Label>
              <Input placeholder="prod, web" {...field("tags")} />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={add.isPending}>
                {add.isPending ? "Adding…" : "Add Server"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
