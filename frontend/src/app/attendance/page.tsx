"use client";

import { Download, Search } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { PageHeader } from "@/components/app-shell";
import { useSession } from "@/components/session-provider";
import {
  Button,
  Card,
  CardBody,
  EmptyState,
  ErrorState,
  Input,
  Label,
  LoadingState,
  Metric,
  Pagination,
  Select,
  StatusBadge,
  Table,
  Td,
  Th,
} from "@/components/ui/primitives";
import { downloadUrl } from "@/lib/api";
import type { PaginatedAttendance, SubjectAnalytics } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { pct } from "@/lib/utils";

type SortKey = "percentage" | "name" | "roll_number" | "attended";

export default function AttendancePage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <AttendanceView />
    </Suspense>
  );
}

function AttendanceView() {
  const { teacher } = useSession();
  const params = useSearchParams();
  const subjects = useMemo(() => teacher?.subject_codes ?? [], [teacher]);

  // The subject comes from the URL when it names one this teacher may see,
  // otherwise it is whatever they have picked, falling back to their first.
  const requested = params.get("subject");
  const [picked, setPicked] = useState("");
  const subject =
    picked ||
    (requested && subjects.includes(requested) ? requested : subjects[0]) ||
    "";

  const [division, setDivision] = useState("");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [belowOnly, setBelowOnly] = useState(false);
  const [sortBy, setSortBy] = useState<SortKey>("percentage");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  // Reset to page 1 whenever the filters change, during render rather than in
  // an effect, so there is no second render pass with a stale page number.
  const filterKey = `${subject}|${division}|${debounced}|${belowOnly}|${sortBy}|${sortDir}`;
  const [lastFilterKey, setLastFilterKey] = useState(filterKey);
  if (filterKey !== lastFilterKey) {
    setLastFilterKey(filterKey);
    setPage(1);
  }

  const query = useMemo(() => {
    const q = new URLSearchParams({
      page: String(page),
      page_size: "25",
      sort_by: sortBy,
      sort_dir: sortDir,
    });
    if (division) q.set("division", division);
    if (debounced.trim()) q.set("search", debounced.trim());
    if (belowOnly) q.set("below_only", "true");
    return q.toString();
  }, [page, sortBy, sortDir, division, debounced, belowOnly]);

  const rows = useApi<PaginatedAttendance>(
    subject
      ? `/api/subjects/${encodeURIComponent(subject)}/attendance?${query}`
      : null,
  );
  const stats = useApi<SubjectAnalytics>(
    subject ? `/api/subjects/${encodeURIComponent(subject)}/analytics` : null,
  );

  function toggleSort(key: SortKey) {
    if (sortBy === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortBy(key);
      setSortDir("asc");
    }
  }

  function exportCsv() {
    const q = new URLSearchParams();
    if (division) q.set("division", division);
    if (debounced.trim()) q.set("search", debounced.trim());
    if (belowOnly) q.set("below_only", "true");
    window.location.href = downloadUrl(
      `/api/subjects/${encodeURIComponent(subject)}/attendance.csv?${q}`,
    );
  }

  if (subjects.length === 0) {
    return (
      <>
        <PageHeader title="Attendance Analytics" />
        <Card>
          <EmptyState title="No subjects assigned to you" />
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Attendance Analytics"
        description={`Attendance is computed as classes attended ÷ classes conducted × 100. The ${teacher?.attendance_threshold ?? 75}% threshold is an illustrative application setting, not a college regulation.`}
        actions={
          subject ? (
            <Button variant="outline" size="sm" onClick={exportCsv}>
              <Download className="h-3.5 w-3.5" />
              Export CSV
            </Button>
          ) : null
        }
      />

      {/* Filters */}
      <Card className="mb-3">
        <CardBody className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <Label htmlFor="subject">Subject</Label>
            <Select
              id="subject"
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
            <Label htmlFor="division">Division</Label>
            <Select
              id="division"
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
            <Label htmlFor="search">Search student</Label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-[var(--muted-foreground)]" />
              <Input
                id="search"
                className="pl-8"
                placeholder="Name or roll number"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
          <div className="flex items-end">
            <label className="flex h-9 cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={belowOnly}
                onChange={(e) => setBelowOnly(e.target.checked)}
                className="h-4 w-4 accent-[var(--accent)]"
              />
              Below threshold only
            </label>
          </div>
        </CardBody>
      </Card>

      {/* Aggregates */}
      {stats.data && (
        <div className="mb-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Metric
            label="Enrolled students"
            value={stats.data.enrolled_students}
            hint={`${stats.data.classes_conducted} classes conducted`}
          />
          <Metric
            label="Pooled attendance"
            value={pct(stats.data.class_attendance_percentage, 2)}
            hint="Total attended ÷ total conducted"
          />
          <Metric
            label="Below threshold"
            value={stats.data.students_below_threshold}
            tone={stats.data.students_below_threshold > 0 ? "danger" : "success"}
            hint={`${stats.data.students_meeting_threshold} meeting it`}
          />
          <Metric
            label="Range"
            value={`${pct(stats.data.lowest_percentage, 0)} – ${pct(stats.data.highest_percentage, 0)}`}
            hint="Lowest to highest student"
          />
        </div>
      )}

      {/* Table */}
      <Card>
        {rows.loading && <LoadingState label="Loading attendance…" />}
        {rows.error && (
          <div className="p-4">
            <ErrorState message={rows.error} onRetry={rows.reload} />
          </div>
        )}

        {rows.data && rows.data.items.length === 0 && (
          <EmptyState
            title="No students match these filters"
            description="Try clearing the search box or the division filter."
          />
        )}

        {rows.data && rows.data.items.length > 0 && (
          <>
            <Table>
              <thead>
                <tr>
                  <Th
                    sortable
                    active={sortBy === "roll_number"}
                    direction={sortDir}
                    onClick={() => toggleSort("roll_number")}
                  >
                    Roll number
                  </Th>
                  <Th
                    sortable
                    active={sortBy === "name"}
                    direction={sortDir}
                    onClick={() => toggleSort("name")}
                  >
                    Student
                  </Th>
                  <Th>ID</Th>
                  <Th>Div</Th>
                  <Th
                    className="text-right"
                    sortable
                    active={sortBy === "attended"}
                    direction={sortDir}
                    onClick={() => toggleSort("attended")}
                  >
                    Attended
                  </Th>
                  <Th className="text-right">Conducted</Th>
                  <Th
                    className="text-right"
                    sortable
                    active={sortBy === "percentage"}
                    direction={sortDir}
                    onClick={() => toggleSort("percentage")}
                  >
                    Attendance
                  </Th>
                  <Th>Status</Th>
                </tr>
              </thead>
              <tbody>
                {rows.data.items.map((r) => (
                  <tr key={r.student_id} className="hover:bg-[var(--surface-muted)]">
                    <Td className="font-mono text-xs">{r.roll_number}</Td>
                    <Td className="font-medium">{r.full_name}</Td>
                    <Td className="font-mono text-xs text-[var(--muted-foreground)]">
                      {r.student_id}
                    </Td>
                    <Td>{r.division}</Td>
                    <Td className="text-right tabular-nums">{r.classes_attended}</Td>
                    <Td className="text-right tabular-nums">
                      {r.classes_conducted}
                    </Td>
                    <Td className="text-right font-medium tabular-nums">
                      {pct(r.attendance_percentage, 2)}
                    </Td>
                    <Td>
                      <StatusBadge status={r.status} />
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <Pagination
              page={rows.data.page}
              totalPages={rows.data.total_pages}
              total={rows.data.total}
              onPage={setPage}
            />
          </>
        )}
      </Card>
    </>
  );
}
