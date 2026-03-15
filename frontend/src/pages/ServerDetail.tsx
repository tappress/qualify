import { useState } from "react"
import { useParams, useNavigate, Link } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { api } from "@/lib/api"
import type { Server, CheckResult, Environment, Project } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import {
  ArrowLeft, Wifi, CheckCircle, AlertCircle, XCircle, MinusCircle,
  RefreshCw, HardDrive, Server as ServerIcon, ChevronRight, Terminal,
} from "lucide-react"

// ── Preflight check icon ──────────────────────────────────────────────────────

function CheckIcon({ status }: { status: CheckResult["status"] }) {
  if (status === "pass") return <CheckCircle size={14} className="text-emerald-500 shrink-0" />
  if (status === "warn") return <AlertCircle size={14} className="text-amber-400 shrink-0" />
  if (status === "fail") return <XCircle size={14} className="text-red-500 shrink-0" />
  return <MinusCircle size={14} className="text-zinc-500 shrink-0" />
}

// ── Server status badge ───────────────────────────────────────────────────────

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
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium ${s.bg} ${s.text}`}>
      <span className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${s.dot}`} />
      {s.label}
    </span>
  )
}

// ── Info row ──────────────────────────────────────────────────────────────────

function InfoRow({ label, value, mono = false }: { label: string; value?: string | null; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground uppercase tracking-wider font-medium">{label}</span>
      <span className={`text-sm ${mono ? "font-mono text-xs" : ""} ${value ? "text-foreground" : "text-muted-foreground/50"}`}>
        {value || "—"}
      </span>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ServerDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; latency_ms?: number } | null>(null)

  const { data: server, isLoading } = useQuery<Server>({
    queryKey: ["server", id],
    queryFn: () => api.get(`/servers/${id}`).then((r) => r.data),
    enabled: !!id,
  })

  const { data: allEnvs } = useQuery<Environment[]>({
    queryKey: ["environments"],
    queryFn: () => api.get("/environments/").then((r) => r.data),
  })

  const { data: projects } = useQuery<Project[]>({
    queryKey: ["projects"],
    queryFn: () => api.get("/projects/").then((r) => r.data),
  })


  const testConn = useMutation({
    mutationFn: () => api.post(`/servers/${id}/test-connection`).then((r) => r.data),
    onSuccess: (data) => setTestResult(data),
    onError: () => toast.error("Connection test failed"),
  })

  const bootstrap = useMutation({
    mutationFn: () => api.post(`/servers/${id}/bootstrap`).then((r) => r.data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["server", id] })
      toast.success(`Bootstrap complete — ${data.os.name} ${data.os.version}`)
    },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? "Bootstrap failed"),
  })

  const qualify = useMutation({
    mutationFn: () => api.post(`/servers/${id}/qualify`).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["server", id] })
      toast.success("Health check complete")
    },
    onError: () => toast.error("Health check failed"),
  })

  const envs = allEnvs?.filter((e) => e.server_id === id) ?? []

  if (isLoading) {
    return (
      <div className="p-6 max-w-3xl mx-auto space-y-4">
        <Skeleton className="h-10 w-48 bg-card" />
        <Skeleton className="h-40 w-full bg-card" />
      </div>
    )
  }
  if (!server) {
    return (
      <div className="p-6 text-muted-foreground text-sm">Server not found.</div>
    )
  }

  const isBusy = bootstrap.isPending || qualify.isPending || testConn.isPending

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">

      {/* ── Top bar ── */}
      <div className="flex items-start gap-3">
        <button
          onClick={() => navigate("/servers")}
          className="mt-0.5 p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
        >
          <ArrowLeft size={16} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-semibold tracking-tight">{server.name}</h1>
            {server.status !== "unknown" && <ServerStatusBadge status={server.status} />}
          </div>
          <p className="text-xs text-muted-foreground font-mono mt-1">
            {server.user}@{server.host}:{server.port}
          </p>
        </div>
      </div>

      {/* ── Action buttons ── */}
      <div className="flex gap-3 flex-wrap">
        <Button
          variant="outline"
          className="h-10 gap-2 border-border"
          onClick={() => testConn.mutate()}
          disabled={isBusy}
        >
          <Wifi size={15} className={testConn.isPending ? "animate-pulse" : ""} />
          {testConn.isPending ? "Testing…" : "Test Connection"}
        </Button>

        <Button
          variant="outline"
          className="h-10 gap-2 border-border"
          onClick={() => bootstrap.mutate()}
          disabled={isBusy || server.status === "bootstrapping"}
        >
          <HardDrive size={15} className={bootstrap.isPending ? "animate-pulse" : ""} />
          {bootstrap.isPending
            ? "Bootstrapping…"
            : server.bootstrapped_at
            ? "Re-bootstrap"
            : "Bootstrap"}
        </Button>

        <Button
          className="h-10 gap-2"
          onClick={() => qualify.mutate()}
          disabled={isBusy || server.status === "qualifying"}
        >
          <RefreshCw size={15} className={qualify.isPending ? "animate-spin" : ""} />
          {qualify.isPending ? "Checking…" : "Run Health Check"}
        </Button>
      </div>

      {/* ── Command log link ── */}
      <Link
        to={`/servers/${id}/log`}
        className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <Terminal size={12} />
        View command log
        <ChevronRight size={11} className="opacity-50" />
      </Link>

      {/* ── Last error ── */}
      {(server.status === "bootstrap_failed" || server.status === "failed") && server.last_error && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-3 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-red-400 text-xs font-semibold uppercase tracking-wider">
              <XCircle size={13} />
              {server.status === "bootstrap_failed" ? "Bootstrap failed" : "Health check failed"}
            </div>
            <a
              href={`https://github.com/tappress/qualify/issues/new?title=${encodeURIComponent("Bootstrap failed: " + server.last_error.split("\n")[0].slice(0, 80))}&body=${encodeURIComponent("**OS:** " + (server.os_name ? `${server.os_name} ${server.os_version ?? ""}`.trim() : "unknown") + "\n\n**Error:**\n```\n" + server.last_error + "\n```")}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-red-500/15 text-red-300 hover:bg-red-500/25 border border-red-500/20 transition-colors shrink-0"
            >
              Report issue ↗
            </a>
          </div>
          <pre className="text-xs text-red-300/80 font-mono whitespace-pre-wrap break-all leading-relaxed">
            {server.last_error}
          </pre>
        </div>
      )}

      {/* ── Connection test result ── */}
      {testResult && (
        <div
          className={`flex items-center gap-2.5 px-4 py-3 rounded-lg text-sm border ${
            testResult.success
              ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
              : "bg-red-500/10 border-red-500/20 text-red-400"
          }`}
        >
          {testResult.success ? (
            <CheckCircle size={15} className="shrink-0" />
          ) : (
            <XCircle size={15} className="shrink-0" />
          )}
          <span>
            {testResult.message}
            {testResult.latency_ms != null && (
              <span className="ml-2 font-mono text-xs opacity-70">
                {testResult.latency_ms.toFixed(0)}ms
              </span>
            )}
          </span>
        </div>
      )}

      {/* ── Server info ── */}
      <div className="bg-card border border-border rounded-lg">
        <div className="px-4 py-3 border-b border-border">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Server Info
          </h2>
        </div>
        <div className="grid grid-cols-2 gap-px bg-border">
          {[
            { label: "Public IP",     value: server.public_ip,   mono: true },
            { label: "OS",            value: server.os_name ? `${server.os_name} ${server.os_version ?? ""}`.trim() : null },
            { label: "Auth Method",   value: server.auth_method },
            { label: "SSH Key",       value: server.ssh_key_path, mono: true },
            { label: "Bootstrapped",  value: server.bootstrapped_at
                ? new Date(server.bootstrapped_at).toLocaleString()
                : "Never" },
            { label: "Last Preflight", value: server.last_qualified_at
                ? new Date(server.last_qualified_at).toLocaleString()
                : "Never" },
          ].map(({ label, value, mono }) => (
            <div key={label} className="bg-card px-4 py-3">
              <InfoRow label={label} value={value} mono={mono} />
            </div>
          ))}
        </div>
      </div>

      {/* ── Preflight results ── */}
      {server.qualify_results.length > 0 && (
        <div className="bg-card border border-border rounded-lg">
          <div className="px-4 py-3 border-b border-border">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Health Check Results
            </h2>
          </div>
          <div className="divide-y divide-border">
            {server.qualify_results.map((r) => (
              <div key={r.check} className="flex items-start gap-3 px-4 py-3">
                <CheckIcon status={r.status} />
                <div className="min-w-0">
                  <span className="text-sm font-medium">{r.check}</span>
                  <span className="text-sm text-muted-foreground ml-2">{r.message}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Environments ── */}
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Environments on this server
        </h2>

        {envs.length === 0 ? (
          <div className="border border-dashed border-border rounded-lg py-10 text-center">
            <ServerIcon size={20} className="text-muted-foreground/30 mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">No environments deployed here yet.</p>
          </div>
        ) : (
          <div className="border border-border rounded-lg overflow-hidden bg-card">
            {envs.map((env, i) => {
              const project = projects?.find((p) => p.id === env.project_id)
              return (
                <Link
                  key={env.id}
                  to={`/projects/${env.project_id}`}
                  className={`flex items-center justify-between px-4 py-3.5 hover:bg-muted/30 transition-colors ${i > 0 ? "border-t border-border" : ""}`}
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium leading-tight">
                      {project?.name ?? (
                        <span className="font-mono text-xs">{env.project_id.slice(0, 8)}</span>
                      )}
                      <span className="text-muted-foreground font-normal"> / {env.name}</span>
                    </p>
                    <p className="text-xs text-muted-foreground font-mono mt-0.5">
                      {env.domain || "no domain"} · port {env.port}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {env.inferred_infra.postgres && (
                      <Badge variant="secondary" className="text-xs font-mono">postgres</Badge>
                    )}
                    {env.inferred_infra.redis && (
                      <Badge variant="secondary" className="text-xs font-mono">redis</Badge>
                    )}
                    <ChevronRight size={14} className="text-muted-foreground/30 ml-1" />
                  </div>
                </Link>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
