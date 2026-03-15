import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { api } from "@/lib/api"
import type { Deployment, Server, Project } from "@/lib/types"
import { Skeleton } from "@/components/ui/skeleton"
import { Server as ServerIcon, FolderCode, Rocket, ChevronRight } from "lucide-react"

// ── Status badge ─────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<string, { dot: string; label: string; bg: string }> = {
  success:   { dot: "bg-emerald-500", label: "text-emerald-400", bg: "bg-emerald-500/10" },
  failed:    { dot: "bg-red-500",     label: "text-red-400",     bg: "bg-red-500/10" },
  running:   { dot: "bg-blue-500 animate-pulse", label: "text-blue-400", bg: "bg-blue-500/10" },
  pending:   { dot: "bg-amber-400",   label: "text-amber-400",   bg: "bg-amber-400/10" },
  cancelled: { dot: "bg-zinc-500",    label: "text-zinc-400",    bg: "bg-zinc-500/10" },
}

function DeployStatusBadge({ status }: { status: Deployment["status"] }) {
  const s = STATUS_STYLES[status] ?? STATUS_STYLES.cancelled
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium ${s.bg} ${s.label}`}>
      <span className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${s.dot}`} />
      {status}
    </span>
  )
}

// ── Time helper ───────────────────────────────────────────────────────────────

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({
  icon: Icon,
  label,
  value,
  loading,
}: {
  icon: React.ElementType
  label: string
  value?: number
  loading: boolean
}) {
  return (
    <div className="bg-card border border-border rounded-lg px-5 py-4 flex items-center justify-between">
      <div>
        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider mb-1">{label}</p>
        {loading ? (
          <Skeleton className="h-8 w-10 bg-muted" />
        ) : (
          <p className="text-3xl font-bold tabular-nums">{value ?? 0}</p>
        )}
      </div>
      <div className="p-2.5 rounded-md bg-muted/60">
        <Icon size={18} className="text-muted-foreground" strokeWidth={1.5} />
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const navigate = useNavigate()

  const { data: deployments, isLoading: dLoading } = useQuery<Deployment[]>({
    queryKey: ["deployments"],
    queryFn: () => api.get("/deployments/").then((r) => r.data),
  })
  const { data: servers, isLoading: sLoading } = useQuery<Server[]>({
    queryKey: ["servers"],
    queryFn: () => api.get("/servers/").then((r) => r.data),
  })
  const { data: projects, isLoading: pLoading } = useQuery<Project[]>({
    queryKey: ["projects"],
    queryFn: () => api.get("/projects/").then((r) => r.data),
  })

  const recent = deployments?.slice(0, 10) ?? []

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Control plane overview</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard icon={ServerIcon}  label="Servers"     value={servers?.length}     loading={sLoading} />
        <StatCard icon={FolderCode}  label="Projects"    value={projects?.length}    loading={pLoading} />
        <StatCard icon={Rocket}      label="Deployments" value={deployments?.length} loading={dLoading} />
      </div>

      {/* Recent deployments */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Recent Deployments
          </h2>
        </div>

        {dLoading ? (
          <div className="space-y-px rounded-lg overflow-hidden border border-border">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full rounded-none bg-card" />
            ))}
          </div>
        ) : recent.length === 0 ? (
          <div className="border border-dashed border-border rounded-lg py-12 text-center">
            <Rocket size={22} className="text-muted-foreground/40 mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">No deployments yet.</p>
          </div>
        ) : (
          <div className="border border-border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40">
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">Project</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">Status</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">Strategy</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">When</th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody className="bg-card divide-y divide-border">
                {recent.map((d) => {
                  const project = projects?.find((p) => p.id === d.project_id)
                  return (
                    <tr
                      key={d.id}
                      className="hover:bg-muted/30 cursor-pointer transition-colors"
                      onClick={() => navigate(`/deployments/${d.id}`)}
                    >
                      <td className="px-4 py-3 font-medium">
                        {project?.name ?? (
                          <span className="font-mono text-xs text-muted-foreground">{d.project_id.slice(0, 8)}</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <DeployStatusBadge status={d.status} />
                      </td>
                      <td className="px-4 py-3">
                        <span className="font-mono text-xs text-muted-foreground">{d.build_strategy}</span>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground text-xs tabular-nums">{timeAgo(d.triggered_at)}</td>
                      <td className="px-3 py-3 text-right">
                        <ChevronRight size={14} className="text-muted-foreground/40 inline-block" />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
