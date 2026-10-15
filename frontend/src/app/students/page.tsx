"use client";

import { Search, Users, X } from "lucide-react";
import { Suspense, useEffect, useMemo, useState } from "react";

import { PageHeader } from "@/components/app-shell";
import { useSession } from "@/components/session-provider";
import {
  Badge,
  Button,
  Card,
  CardBody,
  EmptyState,
  ErrorState,
  Input,
  Label,
  LoadingState,
  Pagination,
  Select,
  StatusBadge,
  Table,
  Td,
  Th,
} from "@/components/ui/primitives";
import type {
  Paginated,
  Student,
  StudentAcademicSummary,
  StudentActivities,
} from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { formatDate, pct } from "@/lib/utils";

export default function StudentsPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <StudentsView />
    </Suspense>
  );
}

function StudentsView() {
  const { teacher } = useSession();
  const subjects = useMemo(() => teacher?.subject_codes ?? [], [teacher]);

  const [division, setDivision] = useState("");
  const [subject, setSubject] = useState("");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  // Reset pagination during render when the filters change.
  const filterKey = `${division}|${subject}|${debounced}`;
  const [lastFilterKey, setLastFilterKey] = useState(filterKey);
  if (filterKey !== lastFilterKey) {
    setLastFilterKey(filterKey);
    setPage(1);
  }

  const query = useMemo(() => {
    const q = new URLSearchParams({ page: String(page), page_size: "25" });
    if (division) q.set("division", division);
    if (subject) q.set("subject_code", subject);
    if (debounced.trim()) q.set("search", debounced.trim());
    return q.toString();
  }, [page, division, subject, debounced]);

  const list = useApi<Paginated<Student>>(`/api/teachers/me/students?${query}`);

  return (
    <>
      <PageHeader
        title="Student Directory"
        description="Students enrolled in the subjects you teach. Students outside your teaching scope are not listed, and the backend denies access to them even by direct request."
      />

      <Card className="mb-3">
        <CardBody className="grid gap-3 sm:grid-cols-3">
          <div>
            <Label htmlFor="sdiv">Division</Label>
            <Select
              id="sdiv"
              value={division}
              onChange={(e) => setDivision(e.target.value)}
            >
              <option value="">All divisions</option>
              <option value="A">A</option>
              <option value="B">B</option>
              <option value="C">C</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="ssub">Enrolled in subject</Label>
            <Select
              id="ssub"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            >
              <option value="">Any of my subjects</option>
              {subjects.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="ssearch">Search</Label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-[var(--muted-foreground)]" />
              <Input
                id="ssearch"
                className="pl-8"
                placeholder="Name, roll number or ID"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
        </CardBody>
      </Card>

      <Card>
        {list.loading && <LoadingState label="Loading students…" />}
        {list.error && (
          <div className="p-4">
            <ErrorState message={list.error} onRetry={list.reload} />
          </div>
        )}
        {list.data && list.data.items.length === 0 && (
          <EmptyState
            title="No students match these filters"
            icon={<Users className="h-8 w-8" />}
          />
        )}
        {list.data && list.data.items.length > 0 && (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>Roll number</Th>
                  <Th>Student</Th>
                  <Th>ID</Th>
                  <Th>Div</Th>
                  <Th>Skills</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {list.data.items.map((s) => (
                  <tr key={s.student_id} className="hover:bg-[var(--surface-muted)]">
                    <Td className="font-mono text-xs">{s.roll_number}</Td>
                    <Td className="font-medium">{s.full_name}</Td>
                    <Td className="font-mono text-xs text-[var(--muted-foreground)]">
                      {s.student_id}
                    </Td>
                    <Td>{s.division}</Td>
                    <Td>
                      <div className="flex flex-wrap gap-1">
                        {s.skills.slice(0, 3).map((k) => (
                          <Badge key={k}>{k}</Badge>
                        ))}
                        {s.skills.length > 3 && (
                          <span className="text-xs text-[var(--muted-foreground)]">
                            +{s.skills.length - 3}
                          </span>
                        )}
                      </div>
                    </Td>
                    <Td>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setSelected(s.student_id)}
                      >
                        View
                      </Button>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <Pagination
              page={list.data.page}
              totalPages={list.data.total_pages}
              total={list.data.total}
              onPage={setPage}
            />
          </>
        )}
      </Card>

      {selected && (
        <StudentDetail studentId={selected} onClose={() => setSelected(null)} />
      )}
    </>
  );
}

function StudentDetail({
  studentId,
  onClose,
}: {
  studentId: string;
  onClose: () => void;
}) {
  const summary = useApi<StudentAcademicSummary>(
    `/api/students/${encodeURIComponent(studentId)}/academic-summary`,
  );
  const activities = useApi<StudentActivities>(
    `/api/students/${encodeURIComponent(studentId)}/activities`,
  );

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/30"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Student record"
    >
      <div
        className="h-full w-full max-w-2xl overflow-y-auto bg-[var(--surface)] shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 flex items-center justify-between border-b border-[var(--border)] bg-[var(--surface)] px-4 py-3">
          <h2 className="font-semibold">
            {summary.data?.full_name ?? studentId}
          </h2>
          <button onClick={onClose} aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4 p-4">
          {summary.loading && <LoadingState />}
          {summary.error && <ErrorState message={summary.error} />}

          {summary.data && (
            <>
              <div className="flex flex-wrap gap-2 text-sm">
                <Badge>{summary.data.roll_number}</Badge>
                <Badge>Division {summary.data.division}</Badge>
                <Badge>
                  Year {summary.data.academic_year} · Sem{" "}
                  {summary.data.semester}
                </Badge>
              </div>

              <section>
                <h3 className="mb-2 text-sm font-semibold">
                  Attendance in your subjects
                </h3>
                <Table>
                  <thead>
                    <tr>
                      <Th>Subject</Th>
                      <Th className="text-right">Attended</Th>
                      <Th className="text-right">Conducted</Th>
                      <Th className="text-right">%</Th>
                      <Th>Status</Th>
                      <Th className="text-right">Classes to recover</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.data.attendance.map((a) => (
                      <tr key={a.subject_code}>
                        <Td>
                          <span className="font-mono text-xs">
                            {a.subject_code}
                          </span>
                        </Td>
                        <Td className="text-right tabular-nums">
                          {a.classes_attended}
                        </Td>
                        <Td className="text-right tabular-nums">
                          {a.classes_conducted}
                        </Td>
                        <Td className="text-right font-medium tabular-nums">
                          {pct(a.attendance_percentage, 2)}
                        </Td>
                        <Td>
                          <StatusBadge status={a.status} />
                        </Td>
                        <Td className="text-right tabular-nums">
                          {a.classes_needed_for_threshold > 0
                            ? a.classes_needed_for_threshold
                            : "—"}
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
                <p className="mt-1.5 text-xs text-[var(--muted-foreground)]">
                  &ldquo;Classes to recover&rdquo; assumes every future class is
                  attended, to reach {summary.data.threshold}%.
                </p>
              </section>

              <section>
                <h3 className="mb-2 text-sm font-semibold">
                  Assessment results
                  {summary.data.assessments_not_evaluated > 0 && (
                    <span className="ml-2 font-normal text-[var(--muted-foreground)]">
                      ({summary.data.assessments_not_evaluated} not yet
                      evaluated)
                    </span>
                  )}
                </h3>
                <Table>
                  <thead>
                    <tr>
                      <Th>Subject</Th>
                      <Th>Assessment</Th>
                      <Th className="text-right">Marks</Th>
                      <Th>State</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.data.assessments.map((a, i) => (
                      <tr key={i}>
                        <Td className="font-mono text-xs">{a.subject_code}</Td>
                        <Td>{a.title}</Td>
                        <Td className="text-right tabular-nums">
                          {a.marks_obtained === null
                            ? "—"
                            : `${a.marks_obtained} / ${a.max_marks}`}
                        </Td>
                        <Td>
                          <Badge
                            tone={
                              a.evaluation_state === "evaluated"
                                ? "success"
                                : a.evaluation_state === "absent"
                                  ? "danger"
                                  : "warning"
                            }
                          >
                            {a.evaluation_state}
                          </Badge>
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </section>

              <section>
                <h3 className="mb-2 text-sm font-semibold">
                  Assignments
                  {summary.data.overdue_assignment_count > 0 && (
                    <span className="ml-2 font-normal text-[var(--danger)]">
                      ({summary.data.overdue_assignment_count} overdue)
                    </span>
                  )}
                </h3>
                <Table>
                  <thead>
                    <tr>
                      <Th>Assignment</Th>
                      <Th>Due</Th>
                      <Th>Status</Th>
                      <Th className="text-right">Marks</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.data.assignments.map((a) => (
                      <tr key={a.assignment_id}>
                        <Td>{a.title}</Td>
                        <Td>{formatDate(a.due_date)}</Td>
                        <Td>
                          <Badge
                            tone={
                              a.is_overdue
                                ? "danger"
                                : a.status === "evaluated"
                                  ? "success"
                                  : a.status === "submitted"
                                    ? "info"
                                    : "neutral"
                            }
                          >
                            {a.is_overdue ? "overdue" : a.status}
                          </Badge>
                        </Td>
                        <Td className="text-right tabular-nums">
                          {a.marks_obtained === null
                            ? "—"
                            : `${a.marks_obtained} / ${a.max_marks}`}
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </section>

              <section>
                <h3 className="mb-2 text-sm font-semibold">
                  Extracurricular record
                </h3>
                {activities.loading && <LoadingState />}
                {activities.error && <ErrorState message={activities.error} />}
                {activities.data && activities.data.activity_count === 0 && (
                  <p className="text-sm text-[var(--muted-foreground)]">
                    No extracurricular participation recorded.
                  </p>
                )}
                {activities.data && activities.data.activity_count > 0 && (
                  <ul className="space-y-2">
                    {activities.data.activities.map((a, i) => (
                      <li
                        key={i}
                        className="rounded-md border border-[var(--border)] p-3 text-sm"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">{a.title}</span>
                          <Badge>{a.category}</Badge>
                          <Badge tone="info">{a.role}</Badge>
                          {a.achievement && (
                            <Badge tone="success">{a.achievement}</Badge>
                          )}
                        </div>
                        <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                          {formatDate(a.participation_date)} ·{" "}
                          {a.participation_status}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
