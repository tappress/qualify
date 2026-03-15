export interface CheckResult {
  check: string
  status: "pass" | "fail" | "warn" | "skip"
  message: string
  details?: Record<string, unknown>
}

export interface Server {
  id: string
  name: string
  host: string
  port: number
  user: string
  ssh_key_path: string
  tags: string[]
  public_ip?: string
  auth_method?: "key" | "password"
  status: "unknown" | "bootstrapping" | "bootstrap_failed" | "qualified" | "failed" | "qualifying"
  bootstrapped_at?: string
  os_id?: string
  os_name?: string
  os_version?: string
  last_qualified_at?: string
  qualify_results: CheckResult[]
  created_at: string
}

export interface EnvVarRef {
  key: string
  value: string
  is_secret: boolean
  secret_name: string
}

export interface InfraInference {
  postgres: boolean
  redis: boolean
  traefik: boolean
  minio: boolean
  custom_services: string[]
}

export interface EnvVarCheck {
  key: string
  status: "provided" | "will_provision" | "missing"
  note: string
}

export interface Environment {
  id: string
  project_id: string
  name: string
  server_id: string
  domain: string
  port: number
  env_vars: EnvVarRef[]
  inferred_infra: InfraInference
  cloudflare_record_id?: string
  created_at: string
}

export interface Project {
  id: string
  name: string
  git_url: string
  git_branch: string
  build_context: string
  dockerfile_path: string
  env_template_content: string
  build_strategy: "local" | "remote"
  image_name: string
  created_at: string
}

export interface DeploymentStage {
  name: string
  status: "pending" | "running" | "success" | "failed" | "skipped"
  duration_ms?: number
}

export interface Deployment {
  id: string
  project_id: string
  environment_id: string
  triggered_at: string
  completed_at?: string
  status: "pending" | "running" | "success" | "failed" | "cancelled"
  image_tag?: string
  git_sha?: string
  build_strategy: "local" | "remote"
  stages: DeploymentStage[]
  error?: string
}

export interface LogLine {
  deployment_id: string
  timestamp: string
  stage: string
  level: "info" | "warn" | "error"
  message: string
}

export interface AppSettings {
  primary_server_id?: string
  registry: { url: string; username: string }
  cloudflare_token_stored: boolean
  cloudflare_zone_id: string
}
