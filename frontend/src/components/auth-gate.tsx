"use client";

import { GraduationCap, Info, ShieldAlert } from "lucide-react";
import { useState } from "react";

import { AppShell } from "@/components/app-shell";
import { useSession } from "@/components/session-provider";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  LoadingState,
} from "@/components/ui/primitives";
import { useApi } from "@/lib/use-api";
import type { DemoTeacherOption } from "@/lib/types";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { teacher, loading, error, refresh } = useSession();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingState label="Checking your session…" />
      </div>
    );
  }

  if (error && !teacher) {
    return (
      <div className="mx-auto flex min-h-screen max-w-lg items-center justify-center p-4">
        <ErrorState message={error} onRetry={() => void refresh()} />
      </div>
    );
  }

  if (!teacher) return <DemoLogin />;

  return <AppShell>{children}</AppShell>;
}

function DemoLogin() {
  const { signIn } = useSession();
  const { data, loading, error, reload } =
    useApi<DemoTeacherOption[]>("/api/demo-teachers");
  const [pending, setPending] = useState<string | null>(null);
  const [signInError, setSignInError] = useState<string | null>(null);

  async function choose(teacherId: string) {
    setPending(teacherId);
    setSignInError(null);
    try {
      await signIn(teacherId);
    } catch (err) {
      setSignInError(err instanceof Error ? err.message : "Sign-in failed.");
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--background)] px-4 py-10">
      <div className="mx-auto max-w-3xl">
        <div className="mb-6 flex items-center gap-2.5">
          <GraduationCap className="h-6 w-6 text-[var(--accent)]" />
          <div>
            <h1 className="text-lg font-semibold tracking-tight">
              CSBS Faculty Workspace
            </h1>
            <p className="text-sm text-[var(--muted-foreground)]">
              Third-year Computer Science and Business Systems
            </p>
          </div>
        </div>

        <div className="mb-5 flex gap-2.5 rounded-lg border border-[var(--warning)] bg-[var(--warning-soft)] p-3.5 text-sm">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-[var(--warning)]" />
          <div>
            <p className="font-medium text-[var(--warning)]">
              Demonstration sign-in — not real authentication
            </p>
            <p className="mt-1 text-[var(--foreground)]">
              Selecting a name issues a signed demo session. There is no
              password check. Every student record in this application is
              synthetic and must not be treated as an institutional record.
            </p>
          </div>
        </div>

        <Card>
          <div className="border-b border-[var(--border)] px-4 py-3">
            <h2 className="text-sm font-semibold">Continue as faculty member</h2>
            <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
              Your subject access is resolved on the server from the
              teacher–subject assignments in the database.
            </p>
          </div>

          {loading && <LoadingState label="Loading faculty list…" />}
          {error && (
            <div className="p-4">
              <ErrorState message={error} onRetry={reload} />
            </div>
          )}

          {data && (
            <ul className="divide-y divide-[var(--border)]">
              {data.map((t) => (
                <li
                  key={t.teacher_id}
                  className="flex flex-wrap items-center justify-between gap-3 p-4"
                >
                  <div className="min-w-0">
                    <p className="font-medium">{t.full_name}</p>
                    <p className="text-xs text-[var(--muted-foreground)]">
                      {t.designation} · {t.teacher_id}
                    </p>
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {t.subject_codes.map((c) => (
                        <Badge key={c}>{c}</Badge>
                      ))}
                      {t.is_department_coordinator && (
                        <Badge tone="accent">Department coordinator</Badge>
                      )}
                    </div>
                  </div>
                  <Button
                    onClick={() => void choose(t.teacher_id)}
                    disabled={pending !== null}
                  >
                    {pending === t.teacher_id ? "Signing in…" : "Continue"}
                  </Button>
                </li>
              ))}
            </ul>
          )}

          {signInError && (
            <div className="border-t border-[var(--border)] p-4">
              <ErrorState message={signInError} />
            </div>
          )}
        </Card>

        <div className="mt-5 flex gap-2.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3.5 text-xs text-[var(--muted-foreground)]">
          <Info className="mt-0.5 h-4 w-4 shrink-0" />
          <p>
            Each faculty member sees only the subjects assigned to them. The
            backend rejects any request for another teacher&apos;s subject or
            for a student outside their teaching scope, including requests made
            by editing a URL directly.
          </p>
        </div>
      </div>
    </div>
  );
}
