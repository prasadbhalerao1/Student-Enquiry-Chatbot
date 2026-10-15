"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
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
  Input,
  Label,
  LoadingState,
  Metric,
  Pagination,
  Select,
  Table,
  Td,
  Th,
} from "@/components/ui/primitives";
import type { Assessment, PerformanceSummary } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { formatDate, pct } from "@/lib/utils";

export default function PerformancePage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <PerformanceView />
    </Suspense>
  );
}

function PerformanceView() {
  const { teacher } = useSession();
  const params = useSearchParams();
  const subjects = useMemo(() => teacher?.subject_codes ?? [], [teacher]);

  const requested = params.get("subject");
  const [picked, setPicked] = useState("");
  const subject =
    picked ||
    (requested && subjects.includes(requested) ? requested : subjects[0]) ||
    "";

  const [below, setBelow] = useState("");
  const [page, setPage] = useState(1);

  const filterKey = `${subject}|${below}`;
  const [lastFilterKey, setLastFilterKey] = useState(filterKey);
  if (filterKey !== lastFilterKey) {
    setLastFilterKey(filterKey);
    setPage(1);
  }

  const query = useMemo(() => {
    const q = new URLSearchParams({ page: String(page), page_size: "25" });
    const n = Number(below);
    if (below !== "" && Number.isFinite(n) && n >= 0 && n <= 100) {
      q.set("below", String(n));
    }
    return q.toString();
  }, [page, below]);

  const perf = useApi<PerformanceSummary>(
    subject
      ? `/api/subjects/${encodeURIComponent(subject)}/performance?${query}`
      : null,
  );
  const assessments = useApi<Assessment[]>(
    subject ? `/api/subjects/${encodeURIComponent(subject)}/assessments` : null,
  );

  if (subjects.length === 0) {
    return (
      <>
        <PageHeader title="Academic Performance" />
        <Card>
          <EmptyState title="No subjects assigned to you" />
        </Card>
      </>
    );
  }

  const distribution = perf.data
    ? Object.entries(perf.data.distribution).map(([band, count]) => ({
        band,
        count,
      }))
    : [];

  return (
    <>
      <PageHeader
        title="Academic Performance"
        description="Each student's score is the weighted mean of the assessments they were actually evaluated on. Unevaluated work is excluded from the denominator rather than counted as zero."
      />

      <Card className="mb-3">
        <CardBody className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="psub">Subject</Label>
            <Select
              id="psub"
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
            <Label htmlFor="pbelow">Show only students below (%)</Label>
            <Input
              id="pbelow"
              type="number"
              min={0}
              max={100}
              placeholder="e.g. 40"
              value={below}
              onChange={(e) => setBelow(e.target.value)}
            />
          </div>
        </CardBody>
      </Card>

      {perf.loading && <LoadingState label="Loading performance…" />}
      {perf.error && <ErrorState message={perf.error} onRetry={perf.reload} />}

      {perf.data && perf.data.assessment_count === 0 && (
        <Card>
          <EmptyState
            title="No assessments recorded for this subject"
            description="Performance figures appear once assessments exist."
          />
        </Card>
      )}

      {perf.data && perf.data.assessment_count > 0 && (
        <>
          <div className="mb-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric
              label="Class average"
              value={pct(perf.data.class_average_percentage, 2)}
              hint={`${perf.data.evaluated_students ?? 0} students with a score`}
            />
            <Metric label="Assessments" value={perf.data.assessment_count} />
            <Metric
              label="Students listed"
              value={perf.data.total}
              hint={below ? `Below ${below}%` : "All students"}
            />
            <Metric
              label="Awaiting evaluation"
              value={
                assessments.data?.reduce(
                  (n, a) => n + a.pending_evaluation_count,
                  0,
                ) ?? "—"
              }
              hint="Results with no mark recorded"
            />
          </div>

          <div className="mb-3 grid gap-3 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Marks distribution</CardTitle>
              </CardHeader>
              <CardBody>
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={distribution}
                      margin={{ top: 4, right: 8, bottom: 4, left: -20 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="#e5e9ec"
                        vertical={false}
                      />
                      <XAxis
                        dataKey="band"
                        tick={{ fontSize: 11, fill: "#5c6b77" }}
                        unit="%"
                      />
                      <YAxis
                        allowDecimals={false}
                        tick={{ fontSize: 11, fill: "#5c6b77" }}
                      />
                      <Tooltip
                        formatter={(v) => [String(v), "Students"]}
                        contentStyle={{
                          fontSize: 12,
                          borderRadius: 6,
                          border: "1px solid #dfe4e8",
                        }}
                      />
                      <Bar dataKey="count" fill="#0f766e" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Assessments</CardTitle>
              </CardHeader>
              <div className="max-h-56 overflow-y-auto">
                <Table>
                  <thead>
                    <tr>
                      <Th>Assessment</Th>
                      <Th>Date</Th>
                      <Th className="text-right">Avg</Th>
                      <Th className="text-right">Pending</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {assessments.data?.map((a) => (
                      <tr key={a.assessment_id}>
                        <Td>
                          <p className="font-medium">{a.title}</p>
                          <p className="text-xs text-[var(--muted-foreground)]">
                            {a.assessment_type} · {a.max_marks} marks
                          </p>
                        </Td>
                        <Td className="whitespace-nowrap text-xs">
                          {formatDate(a.assessment_date)}
                        </Td>
                        <Td className="text-right tabular-nums">
                          {pct(a.average_percentage, 1)}
                        </Td>
                        <Td className="text-right tabular-nums">
                          {a.pending_evaluation_count}
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </div>
            </Card>
          </div>

          <Card>
            {perf.data.students.length === 0 ? (
              <EmptyState title="No students match this filter" />
            ) : (
              <>
                <Table>
                  <thead>
                    <tr>
                      <Th>Roll number</Th>
                      <Th>Student</Th>
                      <Th>Div</Th>
                      <Th className="text-right">Score</Th>
                      <Th className="text-right">Evaluated</Th>
                      <Th className="text-right">Missing</Th>
                      <Th className="text-right">Absent</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {perf.data.students.map((s) => (
                      <tr
                        key={s.student_id}
                        className="hover:bg-[var(--surface-muted)]"
                      >
                        <Td className="font-mono text-xs">{s.roll_number}</Td>
                        <Td className="font-medium">{s.full_name}</Td>
                        <Td>{s.division}</Td>
                        <Td className="text-right font-medium tabular-nums">
                          {s.performance_percentage === null ? (
                            <Badge tone="warning">No marks yet</Badge>
                          ) : (
                            pct(s.performance_percentage, 1)
                          )}
                        </Td>
                        <Td className="text-right tabular-nums">
                          {s.evaluated_count}
                        </Td>
                        <Td className="text-right tabular-nums">
                          {s.missing_count}
                        </Td>
                        <Td className="text-right tabular-nums">
                          {s.absent_count}
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
                <Pagination
                  page={perf.data.page}
                  totalPages={perf.data.total_pages}
                  total={perf.data.total}
                  onPage={setPage}
                />
              </>
            )}
            {perf.data.calculation_note && (
              <p className="border-t border-[var(--border)] px-4 py-2.5 text-xs text-[var(--muted-foreground)]">
                {perf.data.calculation_note}
              </p>
            )}
          </Card>
        </>
      )}
    </>
  );
}
