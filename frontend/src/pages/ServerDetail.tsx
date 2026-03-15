import { useState } from "react"
import { useParams, useNavigate, Link } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { api } from "@/lib/api"
import type { Server, CheckResult, Environment, Project } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { ArrowLeft, Wifi, CheckCircle, AlertCircle, XCircle, MinusCircle, RefreshCw } from "lucide-react"

function CheckIcon({ status }: { status: CheckResult["status"] }) {
  if (status === "pass") return <CheckCircle size={15} className="text-green-600" />
  if (status === "warn") return <AlertCircle size={15} className="text-yellow-600" />
  if (status === "fail") return <XCircle size={15} className="text-red-600" />
  return <MinusCircle size={15} className="text-gray-400" />
}

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

  const qualify = useMutation({
    mutationFn: () => api.post(`/servers/${id}/qualify`).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["server", id] })
      toast.success("Preflight complete")
    },
    onError: () => toast.error("Preflight failed"),
  })

  const envs = allEnvs?.filter((e) => e.server_id === id) ?? []

  if (isLoading) return <div className="p-6"><Skeleton className="h-48 w-full" /></div>
  if (!server) return <div className="p-6 text-muted-foreground">Server not found.</div>

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate("/servers")}>
          <ArrowLeft size={18} />
        </Button>
        <div>
          <h1 className="text-2xl font-semibold">{server.name}</h1>
          <p className="text-sm text-muted-foreground">{server.user}@{server.host}:{server.port}</p>
        </div>
        <div className="ml-auto flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => testConn.mutate()}
            disabled={testConn.isPending}
          >
            <Wifi size={14} className="mr-1.5" />
            {testConn.isPending ? "Testing…" : "Test Connection"}
          </Button>
          <Button
            size="sm"
            onClick={() => qualify.mutate()}
            disabled={qualify.isPending || server.status === "qualifying"}
          >
            <RefreshCw size={14} className={`mr-1.5 ${qualify.isPending ? "animate-spin" : ""}`} />
            {qualify.isPending ? "Running…" : "Run Preflight"}
          </Button>
        </div>
      </div>

      {/* Connection test result */}
      {testResult && (
        <div className={`flex items-center gap-2 p-3 rounded-md text-sm ${testResult.success ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"}`}>
          {testResult.success ? <CheckCircle size={15} /> : <XCircle size={15} />}
          {testResult.message}
          {testResult.latency_ms != null && ` (${testResult.latency_ms.toFixed(0)}ms)`}
        </div>
      )}

      {/* Server info */}
      <Card>
        <CardHeader><CardTitle className="text-base">Info</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          <div><span className="text-muted-foreground">SSH Key</span><p className="font-mono text-xs mt-0.5">{server.ssh_key_path}</p></div>
          <div><span className="text-muted-foreground">Public IP</span><p className="font-mono text-xs mt-0.5">{server.public_ip ?? "—"}</p></div>
          <div><span className="text-muted-foreground">Status</span><p className="mt-0.5">{server.status}</p></div>
          <div><span className="text-muted-foreground">Last Preflight</span><p className="mt-0.5 text-xs">{server.last_qualified_at ? new Date(server.last_qualified_at).toLocaleString() : "Never"}</p></div>
        </CardContent>
      </Card>

      {/* Preflight results */}
      {server.qualify_results.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Preflight Results</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {server.qualify_results.map((r) => (
              <div key={r.check} className="flex items-start gap-2.5 text-sm">
                <CheckIcon status={r.status} />
                <div>
                  <span className="font-medium">{r.check}</span>
                  <span className="text-muted-foreground ml-2">{r.message}</span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Environments on this server */}
      <div>
        <h2 className="text-base font-medium mb-3">Environments on this server</h2>
        {envs.length === 0 ? (
          <p className="text-sm text-muted-foreground">No environments deployed here yet.</p>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            {envs.map((env, i) => {
              const project = projects?.find((p) => p.id === env.project_id)
              return (
                <Link
                  key={env.id}
                  to={`/projects/${env.project_id}`}
                  className={`flex items-center justify-between px-4 py-3 hover:bg-muted/30 ${i > 0 ? "border-t" : ""}`}
                >
                  <div>
                    <p className="font-medium">{project?.name ?? env.project_id.slice(0, 8)} <span className="text-muted-foreground font-normal">/ {env.name}</span></p>
                    <p className="text-xs text-muted-foreground">{env.domain || "no domain"} · port {env.port}</p>
                  </div>
                  <div className="flex gap-1.5">
                    {env.inferred_infra.postgres && <Badge variant="secondary" className="text-xs">postgres</Badge>}
                    {env.inferred_infra.redis && <Badge variant="secondary" className="text-xs">redis</Badge>}
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
