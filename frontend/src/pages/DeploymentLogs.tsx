import { useEffect, useRef, useState } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api, sseUrl } from "@/lib/api"
import type { Deployment, LogLine, Project } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ArrowLeft, CheckCircle, XCircle, Loader, Clock } from "lucide-react"

function StageStatus({ status }: { status: string }) {
  if (status === "success") return <CheckCircle size={14} className="text-green-600" />
  if (status === "failed") return <XCircle size={14} className="text-red-500" />
  if (status === "running") return <Loader size={14} className="text-blue-500 animate-spin" />
  if (status === "skipped") return <span className="w-3.5 h-3.5 rounded-full border border-gray-300 inline-block" />
  return <Clock size={14} className="text-gray-400" />
}

function DeployBadge({ status }: { status: Deployment["status"] }) {
  const styles: Record<string, string> = {
    success: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
    running: "bg-blue-100 text-blue-800",
    pending: "bg-yellow-100 text-yellow-800",
    cancelled: "bg-gray-100 text-gray-600",
  }
  return (
    <span className={`px-2.5 py-1 rounded text-sm font-medium ${styles[status] ?? styles.cancelled}`}>
      {status}
    </span>
  )
}

function levelClass(level: LogLine["level"]) {
  if (level === "error") return "text-red-400"
  if (level === "warn") return "text-yellow-400"
  return "text-gray-300"
}

export default function DeploymentLogs() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [logs, setLogs] = useState<LogLine[]>([])
  const logEndRef = useRef<HTMLDivElement>(null)
  const sseRef = useRef<EventSource | null>(null)

  const { data: deployment, refetch } = useQuery<Deployment>({
    queryKey: ["deployment", id],
    queryFn: () => api.get(`/deployments/${id}`).then((r) => r.data),
    enabled: !!id,
    refetchInterval: (q) =>
      q.state.data?.status === "running" || q.state.data?.status === "pending" ? 2000 : false,
  })

  const { data: projects } = useQuery<Project[]>({
    queryKey: ["projects"],
    queryFn: () => api.get("/projects/").then((r) => r.data),
  })

  // Load history first, then connect SSE for live tail
  useEffect(() => {
    if (!id) return

    api.get(`/logs/history/${id}`).then((r) => {
      setLogs(r.data)
    })

    const source = new EventSource(sseUrl(`/api/logs/stream/${id}`))
    sseRef.current = source

    source.onmessage = (e) => {
      const line: LogLine = JSON.parse(e.data)
      setLogs((prev) => {
        // Avoid duplicating lines that were already in history
        if (prev.some((l) => l.timestamp === line.timestamp && l.message === line.message)) return prev
        return [...prev, line]
      })
    }

    source.onerror = () => {
      source.close()
      refetch()
    }

    return () => source.close()
  }, [id])

  // Auto-scroll to bottom
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [logs])

  const project = projects?.find((p) => p.id === deployment?.project_id)

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-4 h-screen flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 shrink-0">
        <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
          <ArrowLeft size={18} />
        </Button>
        <div className="flex-1">
          {deployment ? (
            <div className="flex items-center gap-3">
              <div>
                <h1 className="text-lg font-semibold">
                  {project?.name ?? "Deployment"} — {id?.slice(0, 8)}
                </h1>
                <p className="text-xs text-muted-foreground">
                  {new Date(deployment.triggered_at).toLocaleString()}
                  {deployment.git_sha && ` · ${deployment.git_sha.slice(0, 7)}`}
                  {` · ${deployment.build_strategy}`}
                </p>
              </div>
              <DeployBadge status={deployment.status} />
            </div>
          ) : (
            <Skeleton className="h-8 w-64" />
          )}
        </div>
      </div>

      {/* Stage indicators */}
      {deployment?.stages && deployment.stages.length > 0 && (
        <div className="flex items-center gap-1 shrink-0 overflow-x-auto pb-1">
          {deployment.stages.map((stage, i) => (
            <div key={stage.name} className="flex items-center gap-1">
              {i > 0 && <div className="w-4 h-px bg-border" />}
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-muted text-xs">
                <StageStatus status={stage.status} />
                <span className="whitespace-nowrap">{stage.name}</span>
                {stage.duration_ms != null && (
                  <span className="text-muted-foreground">({(stage.duration_ms / 1000).toFixed(1)}s)</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Error banner */}
      {deployment?.error && (
        <div className="shrink-0 flex items-start gap-2 p-3 rounded-md bg-red-50 text-red-800 text-sm">
          <XCircle size={15} className="mt-0.5 shrink-0" />
          <pre className="whitespace-pre-wrap font-mono text-xs">{deployment.error}</pre>
        </div>
      )}

      {/* Log output */}
      <div className="flex-1 min-h-0 bg-zinc-950 rounded-lg overflow-y-auto p-4 font-mono text-xs leading-5">
        {logs.length === 0 && (
          <span className="text-zinc-500">Waiting for logs…</span>
        )}
        {logs.map((line, i) => (
          <div key={i} className={`flex gap-2 ${levelClass(line.level)}`}>
            <span className="text-zinc-600 shrink-0 select-none">{line.timestamp.slice(11, 19)}</span>
            <span className="text-zinc-500 shrink-0 select-none">[{line.stage}]</span>
            <span className="break-all">{line.message}</span>
          </div>
        ))}
        <div ref={logEndRef} />
      </div>
    </div>
  )
}
