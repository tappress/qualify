import { useState } from "react"
import { useParams, useNavigate, Link } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { api } from "@/lib/api"
import type { Project, Environment, Server, Deployment, EnvVarCheck } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { ArrowLeft, Plus, Rocket, CheckCircle, AlertTriangle, XCircle, Globe } from "lucide-react"

function EnvCheckBadge({ status }: { status: EnvVarCheck["status"] }) {
  if (status === "provided") return <CheckCircle size={14} className="text-green-600" />
  if (status === "will_provision") return <span className="text-xs text-blue-600">⚡ auto</span>
  return <XCircle size={14} className="text-red-500" />
}

function DeployStatusBadge({ status }: { status: Deployment["status"] }) {
  const styles: Record<string, string> = {
    success: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
    running: "bg-blue-100 text-blue-800",
    pending: "bg-yellow-100 text-yellow-800",
    cancelled: "bg-gray-100 text-gray-600",
  }
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[status] ?? styles.cancelled}`}>{status}</span>
}

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

// ── Add Environment Dialog ───────────────────────────────────────────────────

function AddEnvDialog({
  projectId,
  servers,
  open,
  onClose,
}: {
  projectId: string
  servers: Server[]
  open: boolean
  onClose: () => void
}) {
  const qc = useQueryClient()
  const [form, setForm] = useState({
    name: "dev", server_id: servers[0]?.id ?? "", domain: "",
    port: "3000", auto_dns: false,
  })

  const add = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(`/projects/${projectId}/envs/`, body).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["envs", projectId] })
      onClose()
      toast.success("Environment created")
    },
    onError: () => toast.error("Failed to create environment"),
  })

  function set(key: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm((f) => ({ ...f, [key]: e.target.value }))
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Environment</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            add.mutate({
              name: form.name,
              server_id: form.server_id,
              domain: form.domain,
              port: parseInt(form.port) || 3000,
              auto_dns: form.auto_dns,
            })
          }}
          className="space-y-3 mt-2"
        >
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Name</Label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs focus:outline-none focus:ring-1 focus:ring-ring"
                value={form.name}
                onChange={set("name")}
              >
                <option value="dev">dev</option>
                <option value="staging">staging</option>
                <option value="prod">prod</option>
              </select>
            </div>
            <div>
              <Label>Server</Label>
              <select
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs focus:outline-none focus:ring-1 focus:ring-ring"
                required
                value={form.server_id}
                onChange={set("server_id")}
              >
                {servers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div>
              <Label>Domain</Label>
              <Input placeholder="dev.myapp.com" value={form.domain} onChange={set("domain")} />
            </div>
            <div>
              <Label>App Port</Label>
              <Input type="number" value={form.port} onChange={set("port")} />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={form.auto_dns}
              onChange={(e) => setForm((f) => ({ ...f, auto_dns: e.target.checked }))}
            />
            Auto-create Cloudflare DNS record
          </label>
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={add.isPending}>
              {add.isPending ? "Creating…" : "Create"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ── Environment Tab ──────────────────────────────────────────────────────────

function EnvTab({ env, project, servers }: { env: Environment; project: Project; servers: Server[] }) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const server = servers.find((s) => s.id === env.server_id)

  const { data: checks } = useQuery<EnvVarCheck[]>({
    queryKey: ["preflight-env", env.id],
    queryFn: () => api.get(`/projects/${project.id}/envs/${env.id}/preflight-env`).then((r) => r.data),
  })

  const { data: deploys } = useQuery<Deployment[]>({
    queryKey: ["env-deploys", env.id],
    queryFn: () => api.get(`/projects/${project.id}/envs/${env.id}/deployments`).then((r) => r.data),
  })

  const deploy = useMutation({
    mutationFn: () =>
      api.post("/deployments/", { project_id: project.id, environment_id: env.id }).then((r) => r.data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["env-deploys", env.id] })
      toast.success("Deployment triggered")
      navigate(`/deployments/${data.id}`)
    },
    onError: () => toast.error("Failed to trigger deployment"),
  })

  const missingCount = checks?.filter((c) => c.status === "missing").length ?? 0

  return (
    <div className="space-y-5">
      {/* Info row */}
      <div className="grid grid-cols-3 gap-4 text-sm">
        <div>
          <p className="text-muted-foreground text-xs mb-0.5">Server</p>
          <p>{server?.name ?? env.server_id.slice(0, 8)}</p>
        </div>
        <div>
          <p className="text-muted-foreground text-xs mb-0.5">Domain</p>
          <p className="flex items-center gap-1">
            {env.domain ? (
              <><Globe size={12} />{env.domain}</>
            ) : (
              <span className="text-muted-foreground">not set</span>
            )}
          </p>
        </div>
        <div>
          <p className="text-muted-foreground text-xs mb-0.5">App Port</p>
          <p>{env.port}</p>
        </div>
      </div>

      {/* Inferred infra */}
      {(env.inferred_infra.postgres || env.inferred_infra.redis || env.inferred_infra.minio) && (
        <div>
          <p className="text-xs text-muted-foreground mb-1.5">Auto-provisioned services</p>
          <div className="flex gap-2">
            {env.inferred_infra.postgres && <Badge variant="secondary">PostgreSQL</Badge>}
            {env.inferred_infra.redis && <Badge variant="secondary">Redis</Badge>}
            {env.inferred_infra.minio && <Badge variant="secondary">MinIO</Badge>}
          </div>
        </div>
      )}

      {/* Env var preflight */}
      {checks && checks.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">
            Env Var Status
            {missingCount > 0 && (
              <span className="ml-2 text-red-600">
                <AlertTriangle size={12} className="inline mr-0.5" />{missingCount} missing
              </span>
            )}
          </p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            {checks.map((c) => (
              <div key={c.key} className="flex items-center gap-2 text-sm">
                <EnvCheckBadge status={c.status} />
                <span className="font-mono text-xs">{c.key}</span>
                {c.note && <span className="text-xs text-muted-foreground">{c.note}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Deploy button */}
      <div className="flex items-center gap-3">
        <Button
          onClick={() => deploy.mutate()}
          disabled={deploy.isPending || missingCount > 0}
          className="gap-2"
        >
          <Rocket size={15} />
          {deploy.isPending ? "Deploying…" : "Deploy"}
        </Button>
        {missingCount > 0 && (
          <p className="text-sm text-muted-foreground">
            Fill in {missingCount} missing env var{missingCount > 1 ? "s" : ""} to deploy.
          </p>
        )}
      </div>

      {/* Deployment history */}
      {deploys && deploys.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">Deployment History</p>
          <div className="border rounded-md overflow-hidden">
            {deploys.slice(0, 5).map((d, i) => (
              <Link
                key={d.id}
                to={`/deployments/${d.id}`}
                className={`flex items-center justify-between px-3 py-2.5 hover:bg-muted/30 text-sm ${i > 0 ? "border-t" : ""}`}
              >
                <div className="flex items-center gap-2">
                  <DeployStatusBadge status={d.status} />
                  <span className="text-muted-foreground text-xs font-mono">{d.git_sha?.slice(0, 7) ?? "—"}</span>
                </div>
                <span className="text-xs text-muted-foreground">{timeAgo(d.triggered_at)}</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [addEnvOpen, setAddEnvOpen] = useState(false)

  const { data: project, isLoading } = useQuery<Project>({
    queryKey: ["project", id],
    queryFn: () => api.get(`/projects/${id}`).then((r) => r.data),
    enabled: !!id,
  })

  const { data: envs = [] } = useQuery<Environment[]>({
    queryKey: ["envs", id],
    queryFn: () => api.get(`/projects/${id}/envs/`).then((r) => r.data),
    enabled: !!id,
  })

  const { data: servers = [] } = useQuery<Server[]>({
    queryKey: ["servers"],
    queryFn: () => api.get("/servers/").then((r) => r.data),
  })

  if (isLoading) return <div className="p-6"><Skeleton className="h-48 w-full" /></div>
  if (!project) return <div className="p-6 text-muted-foreground">Project not found.</div>

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate("/projects")}>
          <ArrowLeft size={18} />
        </Button>
        <div>
          <h1 className="text-2xl font-semibold">{project.name}</h1>
          <p className="text-sm text-muted-foreground font-mono">{project.git_url} ({project.git_branch})</p>
        </div>
      </div>

      {/* Project meta */}
      <Card>
        <CardHeader><CardTitle className="text-base">Build Config</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-3 gap-4 text-sm">
          <div><p className="text-muted-foreground text-xs mb-0.5">Strategy</p><p>{project.build_strategy}</p></div>
          <div><p className="text-muted-foreground text-xs mb-0.5">Dockerfile</p><p className="font-mono text-xs">{project.dockerfile_path}</p></div>
          <div><p className="text-muted-foreground text-xs mb-0.5">Build Context</p><p className="font-mono text-xs">{project.build_context}</p></div>
        </CardContent>
      </Card>

      {/* Environments */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-medium">Environments</h2>
          <Button size="sm" variant="outline" onClick={() => setAddEnvOpen(true)}>
            <Plus size={14} className="mr-1" /> Add Environment
          </Button>
        </div>

        {envs.length === 0 ? (
          <div className="text-center py-10 border rounded-lg text-muted-foreground">
            <p className="mb-2">No environments yet.</p>
            <Button size="sm" variant="outline" onClick={() => setAddEnvOpen(true)}>
              Add your first environment
            </Button>
          </div>
        ) : (
          <Tabs defaultValue={envs[0]?.id}>
            <TabsList>
              {envs.map((e) => (
                <TabsTrigger key={e.id} value={e.id}>{e.name}</TabsTrigger>
              ))}
            </TabsList>
            {envs.map((e) => (
              <TabsContent key={e.id} value={e.id} className="mt-4">
                <EnvTab env={e} project={project} servers={servers} />
              </TabsContent>
            ))}
          </Tabs>
        )}
      </div>

      {servers.length > 0 && (
        <AddEnvDialog
          projectId={id!}
          servers={servers}
          open={addEnvOpen}
          onClose={() => setAddEnvOpen(false)}
        />
      )}
    </div>
  )
}
