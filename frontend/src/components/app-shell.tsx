"use client";

import {
  BarChart3,
  BookOpen,
  CalendarCheck,
  ClipboardList,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  Settings,
  Trophy,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { useSession } from "@/components/session-provider";
import { Badge, Button } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Faculty Dashboard", icon: LayoutDashboard },
  { href: "/subjects", label: "My Subjects", icon: BookOpen },
  { href: "/attendance", label: "Attendance Analytics", icon: CalendarCheck },
  { href: "/students", label: "Student Directory", icon: Users },
  { href: "/performance", label: "Academic Performance", icon: BarChart3 },
  { href: "/assignments", label: "Assignments", icon: ClipboardList },
  { href: "/extracurricular", label: "Extracurricular", icon: Trophy },
  { href: "/assistant", label: "AI Assistant", icon: MessageSquare },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { teacher, signOut } = useSession();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <div className="flex min-h-screen flex-col">
      {/* A persistent, honest statement about what this data is. */}
      <div className="bg-[var(--warning-soft)] px-4 py-1.5 text-center text-xs text-[var(--warning)]">
        <strong className="font-semibold">Demonstration system.</strong> All
        student records are synthetic. Faculty sign-in is a demo selector, not
        real authentication.
      </div>

      <div className="flex flex-1">
        {/* Sidebar */}
        <aside
          className={cn(
            "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-[var(--border)] bg-[var(--surface)] transition-transform lg:static lg:translate-x-0",
            open ? "translate-x-0" : "-translate-x-full",
          )}
        >
          <div className="flex h-14 items-center justify-between border-b border-[var(--border)] px-4">
            <Link href="/" className="flex items-center gap-2">
              <GraduationCap className="h-5 w-5 text-[var(--accent)]" />
              <span className="text-sm font-semibold">Faculty Workspace</span>
            </Link>
            <button
              className="lg:hidden"
              onClick={() => setOpen(false)}
              aria-label="Close navigation"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <nav className="flex-1 overflow-y-auto p-2" aria-label="Main">
            <ul className="space-y-0.5">
              {NAV.map(({ href, label, icon: Icon }) => {
                const active =
                  href === "/" ? pathname === "/" : pathname.startsWith(href);
                return (
                  <li key={href}>
                    <Link
                      href={href}
                      onClick={() => setOpen(false)}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
                        active
                          ? "bg-[var(--accent-soft)] font-medium text-[var(--accent-hover)]"
                          : "text-[var(--muted-foreground)] hover:bg-[var(--surface-muted)] hover:text-[var(--foreground)]",
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      {label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          {/* Signed-in faculty identity and resolved scope. */}
          {teacher && (
            <div className="border-t border-[var(--border)] p-3">
              <p className="truncate text-sm font-medium">{teacher.full_name}</p>
              <p className="truncate text-xs text-[var(--muted-foreground)]">
                {teacher.designation}
              </p>
              <div className="mt-2 flex flex-wrap gap-1">
                {teacher.subject_codes.map((code) => (
                  <Badge key={code} tone="neutral">
                    {code}
                  </Badge>
                ))}
                {teacher.is_department_coordinator && (
                  <Badge tone="accent">Coordinator</Badge>
                )}
              </div>
              <Button
                variant="outline"
                size="sm"
                className="mt-3 w-full"
                onClick={() => void signOut()}
              >
                <LogOut className="h-3.5 w-3.5" />
                Sign out
              </Button>
            </div>
          )}
        </aside>

        {open && (
          <div
            className="fixed inset-0 z-30 bg-black/30 lg:hidden"
            onClick={() => setOpen(false)}
            aria-hidden
          />
        )}

        {/* Main column */}
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-14 items-center gap-3 border-b border-[var(--border)] bg-[var(--surface)] px-4 lg:hidden">
            <button onClick={() => setOpen(true)} aria-label="Open navigation">
              <Menu className="h-5 w-5" />
            </button>
            <span className="text-sm font-semibold">Faculty Workspace</span>
          </header>

          <main className="min-w-0 flex-1 p-4 lg:p-6">{children}</main>
        </div>
      </div>
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="mt-1 max-w-2xl text-sm text-[var(--muted-foreground)]">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
}
