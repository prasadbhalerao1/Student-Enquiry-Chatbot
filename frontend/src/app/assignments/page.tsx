"use client";

import { ClipboardList } from "lucide-react";
import { Suspense, useMemo, useState } from "react";

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
  Label,
  LoadingState,
  Metric,
  Pagination,
  Select,
  Table,
  Td,
  Th,
} from "@/components/ui/primitives";
import type { AssignmentSummary, OverdueRecord, Paginated } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { formatDate } from "@/lib/utils";

type OverdueResponse = Paginated<OverdueRecord> & {
  as_of_date: string;
  definition: string;
};

export default function AssignmentsPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <AssignmentsView />
    </Suspense>
  );
}

function AssignmentsView() {
  const { teacher } = useSession();
  const subjects = useMemo(() => teacher?.subject_codes ?? [], [teacher]);

  const [picked, setPicked] = useState("");
  const subject = picked || subjects[0] || "";

  const [view, setView] = useState<"all" | "overdue">("all");
  const [page, setPage] = useState(1);

  const filterKey = `${subject}|${view}`;
  const [lastFilterKey, setLastFilterKey] = useState(filterKey);
  if (filterKey !== lastFilterKey) {
    setLastFilterKey(filterKey);
    setPage(1);
  }

  const list = useApi<AssignmentSummary[]>(
    subject && view === "all"
      ? `/api/subjects/${encodeURIComponent(subject)}/assignments`
      : null,
  );

  const overdueQuery = useMemo(() => {
    const q = new URLSearchParams({ page: String(page), page_size: "25" });
    if (subject) q.set("subject_code", subject);
    return q.toString();
  }, [page, subject]);

  const overdue = useApi<OverdueResponse>(
    view === "overdue"
      ? `/api/teachers/me/overdue-assignments?${overdueQuery}`
      : null,
  );

  if (subjects.length === 0) {
    return (
      <>
        <PageHeader title="Assignments" />
        <Card>
          <EmptyState title="No subjects assigned to you" />
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Assignments"
        description="An assignment is overdue only when nothing was submitted and the due date has passed. Work submitted but not yet marked is shown as submitted, never as overdue."
      />

      <Card className="mb-3">
        <CardBody className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="asub">Subject</Label>
            <Select
              id="asub"
              value={subject}
              onChange={(e) => setPicked(e.target.value)}
            >
              {subjects.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="aview">View</Label>
            <Select
              id="aview"
              value={view}
              onChange={(e) => setView(e.target.value as "all" | "overdue")}
            >
              <option value="all">All assignments (rollup)</option>
              <option value="overdue">Overdue submissions (per student)</option>
            </Select>
          </div>
        </CardBody>
      </Card>

      {view === "all" && (
        <>
          {list.loading && <LoadingState label="Loading assignments…" />}
          {list.error && (
            <ErrorState message={list.error} onRetry={list.reload} />
          )}
          {list.data && list.data.length === 0 && (
            <Card>
              <EmptyState
                title="No assignments for this subject"
                icon={<ClipboardList className="h-8 w-8" />}
              />
            </Card>
          )}
          {list.data && list.data.length > 0 && (
            <div className="space-y-3">
              {list.data.map((a) => (
                <Card key={a.assignment_id}>
                  <CardHeader className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <CardTitle>{a.title}</CardTitle>
                      <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
                        {a.description}
                      </p>
                      <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                        Assigned {formatDate(a.assigned_date)} · Due{" "}
                        {formatDate(a.due_date)} · {a.max_marks} marks
                      </p>
                    </div>
                    <Badge tone={a.is_past_due ? "neutral" : "info"}>
                      {a.is_past_due ? "Closed" : "Open"}
                    </Badge>
                  </CardHeader>
                  <CardBody className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                    <Stat label="Students" value={a.total_students} />
                    <Stat
                      label="Evaluated"
                      value={a.evaluated_count}
                      tone="success"
                    />
                    <Stat
                      label="Submitted, unmarked"
                      value={a.submitted_count}
                      tone="info"
                    />
                    {a.is_past_due ? (
                      <Stat
                        label="Overdue"
                        value={a.overdue_count}
                        tone={a.overdue_count > 0 ? "danger" : "success"}
                      />
                    ) : (
                      <Stat
                        label="Not yet submitted"
                        value={a.not_yet_due_pending_count}
                        tone="neutral"
                      />
                    )}
                    <Stat
                      label="Average mark"
                      value={
                        a.average_marks === null
                          ? "—"
                          : `${a.average_marks} / ${a.max_marks}`
                      }
                    />
                  </CardBody>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {view === "overdue" && (
        <>
          {overdue.loading && <LoadingState label="Loading overdue work…" />}
          {overdue.error && (
            <ErrorState message={overdue.error} onRetry={overdue.reload} />
          )}
          {overdue.data && (
            <>
              <div className="mb-3 grid gap-3 sm:grid-cols-2">
                <Metric
                  label="Overdue submissions"
                  value={overdue.data.total}
                  tone={overdue.data.total > 0 ? "danger" : "success"}
                  hint={`As of ${formatDate(overdue.data.as_of_date)}`}
                />
              </div>
              <Card>
                {overdue.data.items.length === 0 ? (
                  <EmptyState title="No overdue submissions" />
                ) : (
                  <>
                    <Table>
                      <thead>
                        <tr>
                          <Th>Roll number</Th>
                          <Th>Student</Th>
                          <Th>Subject</Th>
                          <Th>Assignment</Th>
                          <Th>Due</Th>
                          <Th className="text-right">Days overdue</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {overdue.data.items.map((r, i) => (
                          <tr
                            key={`${r.student_id}-${r.assignment_id}-${i}`}
                            className="hover:bg-[var(--surface-muted)]"
                          >
                            <Td className="font-mono text-xs">
                              {r.roll_number}
                            </Td>
                            <Td className="font-medium">{r.full_name}</Td>
                            <Td className="font-mono text-xs">
                              {r.subject_code}
                            </Td>
                            <Td>{r.title}</Td>
                            <Td className="whitespace-nowrap text-xs">
                              {formatDate(r.due_date)}
                            </Td>
                            <Td className="text-right tabular-nums">
                              {r.days_overdue}
                            </Td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                    <Pagination
                      page={overdue.data.page}
                      totalPages={overdue.data.total_pages}
                      total={overdue.data.total}
                      onPage={setPage}
                    />
                  </>
                )}
                <p className="border-t border-[var(--border)] px-4 py-2.5 text-xs text-[var(--muted-foreground)]">
                  {overdue.data.definition}
                </p>
              </Card>
            </>
          )}
        </>
      )}
    </>
  );
}

function Stat({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: React.ReactNode;
  tone?: "neutral" | "success" | "info" | "danger";
}) {
  const color =
    tone === "success"
      ? "text-[var(--success)]"
      : tone === "info"
        ? "text-[var(--info)]"
        : tone === "danger"
          ? "text-[var(--danger)]"
          : "text-[var(--foreground)]";
  return (
    <div>
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
      <p className={`mt-0.5 text-lg font-semibold tabular-nums ${color}`}>
        {value}
      </p>
    </div>
  );
}
