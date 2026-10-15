"use client";

import {
  AlertTriangle,
  CalendarClock,
  ClipboardList,
  MessageSquare,
  Users,
} from "lucide-react";
import Link from "next/link";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PageHeader } from "@/components/app-shell";
import { useSession } from "@/components/session-provider";
import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  LoadingState,
  Metric,
} from "@/components/ui/primitives";
import type { DashboardData } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { formatDate, pct } from "@/lib/utils";

const QUICK_PROMPTS = [
  "Summarize attendance across my assigned subjects.",
  "Which students have the lowest attendance?",
  "Find students with overdue assignments.",
  "Show students who may need academic support.",
];

export default function DashboardPage() {
  const { teacher } = useSession();
  const { data, loading, error, reload } = useApi<DashboardData>(
    "/api/teachers/me/dashboard",
  );

  if (loading) return <LoadingState label="Loading dashboard…" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return null;

  if (data.subject_count === 0) {
    return (
      <>
        <PageHeader title="Faculty Dashboard" />
        <Card>
          <EmptyState
            title="No subjects are assigned to you"
            description="Subject access comes from the teacher–subject assignments in the database. Ask a department coordinator to assign you a subject."
          />
        </Card>
      </>
    );
  }

  const chartData = data.subject_attendance.map((s) => ({
    code: s.subject_code,
    name: s.subject_name ?? s.subject_code,
    attendance: s.class_attendance_percentage ?? 0,
    below: s.students_below_threshold,
  }));

  return (
    <>
      <PageHeader
        title={`Welcome, ${teacher?.full_name ?? "Faculty"}`}
        description={`Figures are computed from the database for the ${data.subject_count} subject${data.subject_count === 1 ? "" : "s"} assigned to you. Threshold: ${data.threshold}% (illustrative setting).`}
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="Subjects assigned"
          value={data.subject_count}
          hint="From teacher–subject assignments"
        />
        <Metric
          label="Students in scope"
          value={data.student_count}
          hint="Distinct students across your subjects"
        />
        <Metric
          label="Below attendance threshold"
          value={data.students_below_threshold}
          tone={data.students_below_threshold > 0 ? "danger" : "success"}
          hint={`Of ${data.attendance_record_count} student–subject records`}
        />
        <Metric
          label="Overdue assignments"
          value={data.overdue_assignment_count}
          tone={data.overdue_assignment_count > 0 ? "warning" : "success"}
          hint="Not submitted and past due"
        />
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Attendance by subject</CardTitle>
            <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
              {data.calculation_notes?.overall_class_attendance_percentage}
            </p>
          </CardHeader>
          <CardBody>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={chartData}
                  margin={{ top: 4, right: 8, bottom: 4, left: -16 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e9ec" vertical={false} />
                  <XAxis
                    dataKey="code"
                    tick={{ fontSize: 11, fill: "#5c6b77" }}
                    angle={-20}
                    textAnchor="end"
                    height={56}
                    interval={0}
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fontSize: 11, fill: "#5c6b77" }}
                    unit="%"
                  />
                  <Tooltip
                    formatter={(v) => [`${Number(v).toFixed(2)}%`, "Attendance"]}
                    labelFormatter={(code) =>
                      chartData.find((c) => c.code === code)?.name ?? code
                    }
                    contentStyle={{
                      fontSize: 12,
                      borderRadius: 6,
                      border: "1px solid #dfe4e8",
                    }}
                  />
                  <Bar dataKey="attendance" radius={[3, 3, 0, 0]}>
                    {chartData.map((entry) => (
                      <Cell
                        key={entry.code}
                        fill={
                          entry.attendance < data.threshold ? "#b4231f" : "#0f766e"
                        }
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 text-xs text-[var(--muted-foreground)]">
              Bars below the {data.threshold}% threshold are shown in red and
              labelled in the table on the Attendance Analytics page.
            </p>
          </CardBody>
        </Card>

        <div className="space-y-3">
          <Card>
            <CardHeader>
              <CardTitle>Overall attendance</CardTitle>
            </CardHeader>
            <CardBody className="space-y-3 text-sm">
              <div>
                <p className="text-xs text-[var(--muted-foreground)]">
                  Pooled (every class counts equally)
                </p>
                <p className="text-xl font-semibold tabular-nums">
                  {pct(data.overall_class_attendance_percentage, 2)}
                </p>
              </div>
              <div>
                <p className="text-xs text-[var(--muted-foreground)]">
                  Mean per student–subject record
                </p>
                <p className="text-xl font-semibold tabular-nums">
                  {pct(data.overall_mean_student_attendance_percentage, 2)}
                </p>
              </div>
              <p className="border-t border-[var(--border)] pt-2 text-xs text-[var(--muted-foreground)]">
                These two differ when subjects have different class counts.
              </p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Awaiting evaluation</CardTitle>
            </CardHeader>
            <CardBody>
              <p className="text-2xl font-semibold tabular-nums">
                {data.pending_evaluation_count}
              </p>
              <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                Assessment results with no mark recorded. These are unevaluated,
                not zero scores.
              </p>
            </CardBody>
          </Card>
        </div>
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <CalendarClock className="h-4 w-4" />
              Upcoming deadlines
            </CardTitle>
          </CardHeader>
          {data.upcoming_deadlines.length === 0 ? (
            <EmptyState title="No upcoming deadlines" />
          ) : (
            <ul className="divide-y divide-[var(--border)]">
              {data.upcoming_deadlines.map((d) => (
                <li key={d.assignment_id} className="px-4 py-2.5 text-sm">
                  <p className="font-medium">{d.title}</p>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {d.subject_code} · due {formatDate(d.due_date)} (
                    {d.days_until_due} day{d.days_until_due === 1 ? "" : "s"})
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <Users className="h-4 w-4" />
              Recent extracurricular activity
            </CardTitle>
          </CardHeader>
          {data.recent_activities.length === 0 ? (
            <EmptyState title="No recorded activity" />
          ) : (
            <ul className="divide-y divide-[var(--border)]">
              {data.recent_activities.map((a, i) => (
                <li key={i} className="px-4 py-2.5 text-sm">
                  <p className="font-medium">{a.title}</p>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {a.student_name} · {formatDate(a.participation_date)}
                  </p>
                  {a.achievement && (
                    <Badge tone="success" className="mt-1">
                      {a.achievement}
                    </Badge>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <MessageSquare className="h-4 w-4" />
              Ask the assistant
            </CardTitle>
          </CardHeader>
          <CardBody className="space-y-2">
            {QUICK_PROMPTS.map((p) => (
              <Link
                key={p}
                href={`/assistant?q=${encodeURIComponent(p)}`}
                className="block rounded-md border border-[var(--border)] px-3 py-2 text-sm transition-colors hover:border-[var(--accent)] hover:bg-[var(--accent-soft)]"
              >
                {p}
              </Link>
            ))}
          </CardBody>
        </Card>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Link
          href="/attendance"
          className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[var(--border-strong)] bg-[var(--surface)] px-3 text-xs font-medium hover:bg-[var(--surface-muted)]"
        >
          <AlertTriangle className="h-3.5 w-3.5" />
          Review low attendance
        </Link>
        <Link
          href="/assignments"
          className="inline-flex h-8 items-center gap-1.5 rounded-md border border-[var(--border-strong)] bg-[var(--surface)] px-3 text-xs font-medium hover:bg-[var(--surface-muted)]"
        >
          <ClipboardList className="h-3.5 w-3.5" />
          Review overdue work
        </Link>
      </div>
    </>
  );
}
