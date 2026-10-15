"use client";

import { ArrowRight, BookOpen } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/app-shell";
import {
  Badge,
  Card,
  CardBody,
  EmptyState,
  ErrorState,
  LoadingState,
} from "@/components/ui/primitives";
import type { Subject } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { pct } from "@/lib/utils";

export default function SubjectsPage() {
  const { data, loading, error, reload } = useApi<Subject[]>(
    "/api/teachers/me/subjects",
  );

  return (
    <>
      <PageHeader
        title="My Subjects"
        description="Subjects assigned to you in the central catalogue. Subjects taught by other faculty are not listed and cannot be opened."
      />

      {loading && <LoadingState label="Loading subjects…" />}
      {error && <ErrorState message={error} onRetry={reload} />}

      {data && data.length === 0 && (
        <Card>
          <EmptyState
            title="No subjects assigned"
            description="Your teacher–subject assignments determine what you can access."
            icon={<BookOpen className="h-8 w-8" />}
          />
        </Card>
      )}

      {data && data.length > 0 && (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {data.map((s) => {
            const low =
              s.class_attendance_percentage !== null &&
              s.class_attendance_percentage < 75;
            return (
              <Card key={s.subject_code} className="flex flex-col">
                <CardBody className="flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-mono text-xs text-[var(--muted-foreground)]">
                        {s.subject_code}
                      </p>
                      <h2 className="mt-0.5 font-medium leading-snug">
                        {s.subject_name}
                      </h2>
                    </div>
                    <Badge tone={s.subject_type === "Lab" ? "info" : "neutral"}>
                      {s.subject_type}
                    </Badge>
                  </div>

                  <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                    Faculty: {s.faculty_name ?? "—"} · {s.credits} credit
                    {s.credits === 1 ? "" : "s"}
                  </p>

                  <dl className="mt-3 grid grid-cols-2 gap-3 border-t border-[var(--border)] pt-3 text-sm">
                    <div>
                      <dt className="text-xs text-[var(--muted-foreground)]">
                        Enrolled
                      </dt>
                      <dd className="font-semibold tabular-nums">
                        {s.enrolled_students}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-[var(--muted-foreground)]">
                        Attendance (pooled)
                      </dt>
                      <dd
                        className={`font-semibold tabular-nums ${low ? "text-[var(--danger)]" : ""}`}
                      >
                        {pct(s.class_attendance_percentage)}
                      </dd>
                    </div>
                  </dl>
                </CardBody>

                <div className="flex gap-2 border-t border-[var(--border)] p-3">
                  <Link
                    href={`/attendance?subject=${encodeURIComponent(s.subject_code)}`}
                    className="inline-flex h-8 flex-1 items-center justify-center gap-1 rounded-md border border-[var(--border-strong)] text-xs font-medium hover:bg-[var(--surface-muted)]"
                  >
                    Attendance
                    <ArrowRight className="h-3 w-3" />
                  </Link>
                  <Link
                    href={`/performance?subject=${encodeURIComponent(s.subject_code)}`}
                    className="inline-flex h-8 flex-1 items-center justify-center gap-1 rounded-md border border-[var(--border-strong)] text-xs font-medium hover:bg-[var(--surface-muted)]"
                  >
                    Performance
                    <ArrowRight className="h-3 w-3" />
                  </Link>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </>
  );
}
