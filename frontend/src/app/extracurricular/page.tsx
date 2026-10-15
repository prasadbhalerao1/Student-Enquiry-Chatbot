"use client";

import { Trophy } from "lucide-react";
import { useMemo, useState } from "react";
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
  Label,
  LoadingState,
  Metric,
  Select,
  Table,
  Td,
  Th,
} from "@/components/ui/primitives";
import type { ExtracurricularSummary } from "@/lib/types";
import { useApi } from "@/lib/use-api";

export default function ExtracurricularPage() {
  const { teacher } = useSession();
  const [division, setDivision] = useState("");
  const [scope, setScope] = useState<"mine" | "department">("mine");

  const path = useMemo(() => {
    if (scope === "department") return "/api/department/extracurricular";
    const q = division ? `?division=${division}` : "";
    return `/api/teachers/me/extracurricular${q}`;
  }, [scope, division]);

  const { data, loading, error, reload } = useApi<ExtracurricularSummary>(path);

  const categories = data
    ? Object.entries(data.by_category).map(([name, count]) => ({ name, count }))
    : [];

  const participationRate =
    data && data.students_in_scope > 0
      ? Math.round((data.students_with_activities / data.students_in_scope) * 100)
      : 0;

  return (
    <>
      <PageHeader
        title="Extracurricular Overview"
        description="Aggregate participation for students in your teaching scope. Individual profiles are available from the Student Directory, and only for students you teach."
      />

      <Card className="mb-3">
        <CardBody className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="escope">Reporting scope</Label>
            <Select
              id="escope"
              value={scope}
              onChange={(e) =>
                setScope(e.target.value as "mine" | "department")
              }
            >
              <option value="mine">My students</option>
              {teacher?.is_department_coordinator && (
                <option value="department">
                  Department-wide (coordinator)
                </option>
              )}
            </Select>
            {!teacher?.is_department_coordinator && (
              <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                Department-wide reporting requires the coordinator role.
              </p>
            )}
          </div>
          {scope === "mine" && (
            <div>
              <Label htmlFor="ediv">Division</Label>
              <Select
                id="ediv"
                value={division}
                onChange={(e) => setDivision(e.target.value)}
              >
                <option value="">All divisions</option>
                <option value="A">A</option>
                <option value="B">B</option>
                <option value="C">C</option>
              </Select>
            </div>
          )}
        </CardBody>
      </Card>

      {loading && <LoadingState label="Loading participation…" />}
      {error && <ErrorState message={error} onRetry={reload} />}

      {data && data.students_in_scope === 0 && (
        <Card>
          <EmptyState
            title="No students in scope"
            icon={<Trophy className="h-8 w-8" />}
          />
        </Card>
      )}

      {data && data.students_in_scope > 0 && (
        <>
          <div className="mb-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric
              label="Students in scope"
              value={data.students_in_scope}
            />
            <Metric
              label="Participating"
              value={`${data.students_with_activities} (${participationRate}%)`}
              hint={`${data.students_without_activities} with no record`}
            />
            <Metric
              label="Total participations"
              value={data.total_participations}
            />
            <Metric
              label="Recorded achievements"
              value={data.achievement_count}
              hint="Awards actually present in the data"
            />
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Participation by category</CardTitle>
              </CardHeader>
              <CardBody>
                {categories.length === 0 ? (
                  <EmptyState title="No participation recorded" />
                ) : (
                  <div className="h-72">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={categories}
                        layout="vertical"
                        margin={{ top: 4, right: 16, bottom: 4, left: 24 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke="#e5e9ec"
                          horizontal={false}
                        />
                        <XAxis
                          type="number"
                          allowDecimals={false}
                          tick={{ fontSize: 11, fill: "#5c6b77" }}
                        />
                        <YAxis
                          type="category"
                          dataKey="name"
                          width={120}
                          tick={{ fontSize: 10, fill: "#5c6b77" }}
                        />
                        <Tooltip
                          formatter={(v) => [String(v), "Participations"]}
                          contentStyle={{
                            fontSize: 12,
                            borderRadius: 6,
                            border: "1px solid #dfe4e8",
                          }}
                        />
                        <Bar
                          dataKey="count"
                          fill="#0f766e"
                          radius={[0, 3, 3, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </CardBody>
            </Card>

            <div className="space-y-3">
              <Card>
                <CardHeader>
                  <CardTitle>Roles held</CardTitle>
                </CardHeader>
                <CardBody>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(data.by_role).map(([role, count]) => (
                      <Badge key={role} tone="info">
                        {role}: {count}
                      </Badge>
                    ))}
                    {Object.keys(data.by_role).length === 0 && (
                      <p className="text-sm text-[var(--muted-foreground)]">
                        No roles recorded.
                      </p>
                    )}
                  </div>
                </CardBody>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Most popular activities</CardTitle>
                </CardHeader>
                {data.top_activities.length === 0 ? (
                  <EmptyState title="No activities recorded" />
                ) : (
                  <Table>
                    <thead>
                      <tr>
                        <Th>Activity</Th>
                        <Th className="text-right">Participants</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.top_activities.map((a) => (
                        <tr key={a.title}>
                          <Td>{a.title}</Td>
                          <Td className="text-right tabular-nums">
                            {a.participants}
                          </Td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                )}
              </Card>
            </div>
          </div>

          <p className="mt-3 text-xs text-[var(--muted-foreground)]">
            Participation, leadership roles and awards are counted separately.
            Only achievements actually recorded in the database are shown.
          </p>
        </>
      )}
    </>
  );
}
