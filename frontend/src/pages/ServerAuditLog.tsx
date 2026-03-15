import { useParams, useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { Server, AuditEntry } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ArrowLeft, RefreshCw, CheckCircle, XCircle } from "lucide-react"

const STAGE_COLORS: Record<string, string> = {
  bootstrap: "bg-blue-500/10 text-blue-400",
  preflight:  "bg-violet-500/10 text-violet-400",
}

export default function ServerAuditLog() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data: server } = useQuery<Server>({
    queryKey: ["server", id],
    queryFn: () => api.get(`/servers/${id}`).then((r) => r.data),
    enabled: !!id,
  })

  const { data: log, isLoading, isFetching, refetch } = useQuery<AuditEntry[]>({
    queryKey: ["audit-log", id],
    queryFn: () => api.get(`/servers/${id}/audit-log`).then((r) => r.data),
    enabled: !!id,
    staleTime: 0,
  })

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(`/servers/${id}`)}
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
        >
          <ArrowLeft size={16} />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-semibold tracking-tight">Command Log</h1>
          {server && (
            <p className="text-xs text-muted-foreground font-mono mt-0.5">{server.name}</p>
          )}
        </div>
        <Button
          variant="outline"
          className="h-8 gap-1.5 text-xs"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          <RefreshCw size={12} className={isFetching ? "animate-spin" : ""} />
          Refresh
        </Button>
      </div>

      {/* Log */}
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        {isLoading ? (
          <div className="divide-y divide-border">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="flex gap-3 px-4 py-3">
                <Skeleton className="h-4 w-5 bg-muted shrink-0" />
                <div className="space-y-1.5 flex-1">
                  <Skeleton className="h-3 w-24 bg-muted" />
                  <Skeleton className="h-3 w-full bg-muted" />
                </div>
              </div>
            ))}
          </div>
        ) : !log?.length ? (
          <div className="py-16 text-center">
            <p className="text-sm text-muted-foreground">No commands logged yet.</p>
            <p className="text-xs text-muted-foreground/60 mt-1">Bootstrap or run a health check to populate this log.</p>
          </div>
        ) : (
          <div className="divide-y divide-border/50">
            {[...log].reverse().map((entry, i) => (
              <div key={i} className="flex items-start gap-3 px-4 py-3 hover:bg-muted/20">
                <div className="mt-0.5 shrink-0">
                  {entry.rc === 0
                    ? <CheckCircle size={13} className="text-emerald-500" />
                    : <XCircle size={13} className="text-red-400" />}
                </div>
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-1.5 py-0.5 rounded font-mono shrink-0 ${STAGE_COLORS[entry.stage] ?? "bg-muted text-muted-foreground"}`}>
                      {entry.stage}
                    </span>
                    <span className="text-xs text-muted-foreground/50 font-mono">
                      {new Date(entry.ts).toLocaleString()}
                    </span>
                    {entry.rc !== 0 && (
                      <span className="text-xs font-mono text-red-400">exit {entry.rc}</span>
                    )}
                  </div>
                  <p className="text-xs font-mono text-foreground/80 break-all">{entry.cmd}</p>
                  {entry.err && (
                    <p className="text-xs font-mono text-red-400/80 break-all">{entry.err}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {log && log.length > 0 && (
        <p className="text-xs text-muted-foreground/50 text-right">{log.length} entries · newest first</p>
      )}
    </div>
  )
}
