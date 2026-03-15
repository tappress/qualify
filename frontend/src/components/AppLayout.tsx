import { NavLink, Outlet } from "react-router-dom"
import { LayoutDashboard, Server, FolderCode, Settings } from "lucide-react"
import { cn } from "@/lib/utils"

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/servers", label: "Servers", icon: Server },
  { to: "/projects", label: "Projects", icon: FolderCode },
  { to: "/settings", label: "Settings", icon: Settings },
]

export default function AppLayout() {
  return (
    <div className="dark flex h-screen overflow-hidden bg-background text-foreground">
      {/* Sidebar */}
      <aside className="w-52 shrink-0 border-r border-sidebar-border bg-sidebar text-sidebar-foreground flex flex-col">
        {/* Wordmark */}
        <div className="px-5 h-14 flex items-center border-b border-sidebar-border">
          <span className="font-mono text-sm font-semibold tracking-widest uppercase text-foreground/90 select-none">
            qualify
          </span>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 space-y-0.5">
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                    : "text-sidebar-foreground/50 hover:text-sidebar-foreground hover:bg-sidebar-accent/60",
                )
              }
            >
              <Icon size={15} strokeWidth={1.75} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-sidebar-border">
          <p className="text-xs text-sidebar-foreground/30 font-mono">v0.1.0</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
