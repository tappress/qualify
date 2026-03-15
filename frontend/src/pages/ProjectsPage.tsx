import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { api } from "@/lib/api"
import type { Project } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { Plus, ChevronRight, GitBranch } from "lucide-react"

const defaultForm = {
  name: "", git_url: "", git_branch: "main", build_context: ".",
  dockerfile_path: "Dockerfile", env_template_content: "",
  build_strategy: "local" as const, image_name: "",
}

export default function ProjectsPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(defaultForm)

  const { data: projects, isLoading } = useQuery<Project[]>({
    queryKey: ["projects"],
    queryFn: () => api.get("/projects/").then((r) => r.data),
  })

  const add = useMutation({
    mutationFn: (body: typeof form) => api.post("/projects/", body).then((r) => r.data),
    onSuccess: (project: Project) => {
      qc.invalidateQueries({ queryKey: ["projects"] })
      setOpen(false)
      setForm(defaultForm)
      toast.success("Project created")
      navigate(`/projects/${project.id}`)
    },
    onError: () => toast.error("Failed to create project"),
  })

  function set(key: keyof typeof defaultForm) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm((f) => ({ ...f, [key]: e.target.value }))
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold">Projects</h1>
        <Button size="sm" onClick={() => setOpen(true)}>
          <Plus size={16} className="mr-1" /> New Project
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
        </div>
      ) : !projects?.length ? (
        <div className="text-center py-16 text-muted-foreground">
          <p className="mb-2">No projects yet.</p>
          <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
            Create your first project
          </Button>
        </div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          {projects.map((p, i) => (
            <div
              key={p.id}
              className={`flex items-center justify-between px-4 py-3.5 hover:bg-muted/30 cursor-pointer ${i > 0 ? "border-t" : ""}`}
              onClick={() => navigate(`/projects/${p.id}`)}
            >
              <div>
                <p className="font-medium">{p.name}</p>
                <p className="text-sm text-muted-foreground flex items-center gap-1.5 mt-0.5">
                  <GitBranch size={12} />
                  {p.git_url} <span className="text-xs">({p.git_branch})</span>
                </p>
              </div>
              <div className="flex items-center gap-3 text-muted-foreground">
                <span className="text-xs bg-secondary text-secondary-foreground px-1.5 py-0.5 rounded">
                  {p.build_strategy}
                </span>
                <ChevronRight size={16} />
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>New Project</DialogTitle>
          </DialogHeader>
          <form
            onSubmit={(e) => { e.preventDefault(); add.mutate(form) }}
            className="space-y-3 mt-2"
          >
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <Label>Project Name</Label>
                <Input placeholder="my-app" required value={form.name} onChange={set("name")} />
              </div>
              <div className="col-span-2">
                <Label>Git URL</Label>
                <Input placeholder="https://github.com/org/repo.git" required value={form.git_url} onChange={set("git_url")} />
              </div>
              <div>
                <Label>Branch</Label>
                <Input value={form.git_branch} onChange={set("git_branch")} />
              </div>
              <div>
                <Label>Build Strategy</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs focus:outline-none focus:ring-1 focus:ring-ring"
                  value={form.build_strategy}
                  onChange={set("build_strategy")}
                >
                  <option value="local">Local (build on this machine)</option>
                  <option value="remote">Remote (build on server)</option>
                </select>
              </div>
              <div>
                <Label>Build Context</Label>
                <Input value={form.build_context} onChange={set("build_context")} />
              </div>
              <div>
                <Label>Dockerfile Path</Label>
                <Input value={form.dockerfile_path} onChange={set("dockerfile_path")} />
              </div>
              <div className="col-span-2">
                <Label>Image Name <span className="text-muted-foreground text-xs">(optional, defaults to project name)</span></Label>
                <Input placeholder="my-app" value={form.image_name} onChange={set("image_name")} />
              </div>
            </div>
            <div>
              <Label>.env.template content <span className="text-muted-foreground text-xs">(paste to auto-detect services)</span></Label>
              <Textarea
                className="font-mono text-xs h-28"
                placeholder={"DATABASE_URL=\nREDIS_URL=\nSECRET_KEY="}
                value={form.env_template_content}
                onChange={set("env_template_content")}
              />
            </div>
            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={add.isPending}>
                {add.isPending ? "Creating…" : "Create Project"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
