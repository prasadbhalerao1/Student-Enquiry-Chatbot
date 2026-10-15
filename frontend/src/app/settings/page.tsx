"use client";

import {
  AlertCircle,
  Check,
  Eye,
  EyeOff,
  ExternalLink,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/app-shell";
import { useSession } from "@/components/session-provider";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  ErrorState,
  Input,
  Label,
  LoadingState,
  Select,
} from "@/components/ui/primitives";
import { api } from "@/lib/api";
import type { ProviderSpec, ProviderTestResult } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { maskKey } from "@/lib/utils";

export default function SettingsPage() {
  const { teacher, provider, setProvider } = useSession();
  const specs = useApi<ProviderSpec[]>("/api/providers");

  const [providerId, setProviderId] = useState("openai");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<ProviderTestResult | null>(null);

  const spec = useMemo(
    () => specs.data?.find((s) => s.id === providerId),
    [specs.data, providerId],
  );

  // When the provider changes, reset the model and endpoint to its defaults.
  // Done during render so the fields never show the previous provider's values.
  const [lastSpecId, setLastSpecId] = useState<string | null>(null);
  if (spec && spec.id !== lastSpecId) {
    setLastSpecId(spec.id);
    setModel(spec.suggested_models[0] ?? "");
    setBaseUrl(spec.default_base_url ?? "");
    setResult(null);
  }

  const canSubmit =
    model.trim() !== "" && (!spec?.requires_api_key || apiKey.trim() !== "");

  async function testConnection() {
    if (!canSubmit) return;
    setTesting(true);
    setResult(null);
    try {
      const res = await api.post<ProviderTestResult>(
        "/api/providers/test-connection",
        {
          provider: {
            provider: providerId,
            model: model.trim(),
            api_key: apiKey.trim() || undefined,
            base_url: baseUrl.trim() || undefined,
          },
        },
      );
      setResult(res);
    } catch (err) {
      setResult({
        ok: false,
        message: err instanceof Error ? err.message : "The test failed.",
      });
    } finally {
      setTesting(false);
    }
  }

  function activate() {
    if (!canSubmit) return;
    setProvider({
      provider: providerId,
      model: model.trim(),
      api_key: apiKey.trim() || undefined,
      base_url: baseUrl.trim() || undefined,
    });
  }

  function clearCredentials() {
    setApiKey("");
    setResult(null);
    setProvider(null);
  }

  return (
    <>
      <PageHeader
        title="Settings"
        description="Configure the AI provider used by the assistant, and review the access your faculty account has."
      />

      <div className="grid gap-3 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>AI provider</CardTitle>
              <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
                Bring your own key. The dashboard and all data pages work
                without one — a key is only needed for the AI Assistant.
              </p>
            </CardHeader>

            {specs.loading && <LoadingState />}
            {specs.error && (
              <div className="p-4">
                <ErrorState message={specs.error} onRetry={specs.reload} />
              </div>
            )}

            {specs.data && (
              <CardBody className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="prov">Provider</Label>
                    <Select
                      id="prov"
                      value={providerId}
                      onChange={(e) => setProviderId(e.target.value)}
                    >
                      {specs.data.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.label}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="model">Model ID</Label>
                    <Input
                      id="model"
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      placeholder="e.g. gpt-4o-mini"
                      list="model-suggestions"
                    />
                    <datalist id="model-suggestions">
                      {spec?.suggested_models.map((m) => (
                        <option key={m} value={m} />
                      ))}
                    </datalist>
                  </div>
                </div>

                {spec?.requires_api_key && (
                  <div>
                    <Label htmlFor="key">API key</Label>
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <Input
                          id="key"
                          type={showKey ? "text" : "password"}
                          value={apiKey}
                          onChange={(e) => setApiKey(e.target.value)}
                          placeholder="Paste your key"
                          autoComplete="off"
                          spellCheck={false}
                          className="pr-9"
                        />
                        <button
                          type="button"
                          onClick={() => setShowKey((v) => !v)}
                          aria-label={showKey ? "Hide key" : "Show key"}
                          className="absolute right-2 top-2.5 text-[var(--muted-foreground)]"
                        >
                          {showKey ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </button>
                      </div>
                      {spec.api_key_url && (
                        <a
                          href={spec.api_key_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex h-9 items-center gap-1 rounded-md border border-[var(--border-strong)] px-3 text-xs font-medium hover:bg-[var(--surface-muted)]"
                        >
                          Get a key
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                    </div>
                  </div>
                )}

                {spec?.supports_custom_base_url && (
                  <div>
                    <Label htmlFor="url">
                      Endpoint URL
                      {spec.id === "openai_compatible" ? " (required)" : " (optional)"}
                    </Label>
                    <Input
                      id="url"
                      value={baseUrl}
                      onChange={(e) => setBaseUrl(e.target.value)}
                      placeholder={spec.default_base_url ?? "https://…/v1"}
                      spellCheck={false}
                    />
                  </div>
                )}

                {spec?.notes && (
                  <p className="rounded-md bg-[var(--surface-muted)] p-2.5 text-xs text-[var(--muted-foreground)]">
                    {spec.notes}
                  </p>
                )}

                {spec && !spec.supports_tool_calling && (
                  <p className="rounded-md bg-[var(--warning-soft)] p-2.5 text-xs text-[var(--warning)]">
                    This provider does not support tool calling. The assistant
                    will receive an aggregate snapshot instead of running
                    per-student lookups.
                  </p>
                )}

                <div className="flex flex-wrap gap-2 pt-1">
                  <Button
                    variant="outline"
                    onClick={() => void testConnection()}
                    disabled={!canSubmit || testing}
                  >
                    {testing ? "Testing…" : "Test connection"}
                  </Button>
                  <Button onClick={activate} disabled={!canSubmit}>
                    Activate provider
                  </Button>
                  {(apiKey || provider) && (
                    <Button variant="danger" onClick={clearCredentials}>
                      <Trash2 className="h-3.5 w-3.5" />
                      Clear credentials
                    </Button>
                  )}
                </div>

                {result && (
                  <div
                    role="status"
                    className={`rounded-md border p-3 text-sm ${
                      result.ok
                        ? "border-[var(--success)] bg-[var(--success-soft)]"
                        : "border-[var(--danger)] bg-[var(--danger-soft)]"
                    }`}
                  >
                    <p
                      className={`flex items-center gap-1.5 font-medium ${
                        result.ok
                          ? "text-[var(--success)]"
                          : "text-[var(--danger)]"
                      }`}
                    >
                      {result.ok ? (
                        <Check className="h-4 w-4" />
                      ) : (
                        <AlertCircle className="h-4 w-4" />
                      )}
                      {result.ok ? "Connection succeeded" : "Connection failed"}
                    </p>
                    <p className="mt-1">{result.message}</p>
                    {result.ok && result.supports_tool_calling === false && (
                      <p className="mt-1 text-xs">
                        Note: this model does not support tool calling.
                      </p>
                    )}
                  </div>
                )}
              </CardBody>
            )}
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>How your API key is handled</CardTitle>
            </CardHeader>
            <CardBody>
              <ul className="space-y-1.5 text-sm text-[var(--muted-foreground)]">
                <li>• Held in this browser tab&apos;s memory only.</li>
                <li>
                  • Never written to localStorage, a cookie, a URL or the
                  database.
                </li>
                <li>
                  • Sent to the backend only with a chat or test request, used
                  for that call, and discarded.
                </li>
                <li>• Redacted from server logs and from error messages.</li>
                <li>
                  • Cleared when you sign out or reload the page — this is
                  deliberate.
                </li>
              </ul>
            </CardBody>
          </Card>
        </div>

        {/* Identity and permissions */}
        <div className="space-y-3">
          <Card>
            <CardHeader>
              <CardTitle>Active provider</CardTitle>
            </CardHeader>
            <CardBody>
              {provider ? (
                <div className="space-y-1.5 text-sm">
                  <Badge tone="success">
                    <Check className="h-3 w-3" />
                    Active
                  </Badge>
                  <p>
                    <span className="text-[var(--muted-foreground)]">
                      Provider:{" "}
                    </span>
                    {provider.provider}
                  </p>
                  <p className="break-all">
                    <span className="text-[var(--muted-foreground)]">
                      Model:{" "}
                    </span>
                    {provider.model}
                  </p>
                  {provider.api_key && (
                    <p className="font-mono text-xs break-all">
                      {maskKey(provider.api_key)}
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-sm text-[var(--muted-foreground)]">
                  No provider configured. The AI Assistant needs one; every
                  other page works without it.
                </p>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4" />
                Your access
              </CardTitle>
            </CardHeader>
            <CardBody className="space-y-2 text-sm">
              {teacher ? (
                <>
                  <p className="font-medium">{teacher.full_name}</p>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {teacher.designation} · {teacher.teacher_id}
                  </p>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {teacher.email}
                  </p>
                  <div>
                    <p className="mb-1 text-xs font-medium text-[var(--muted-foreground)]">
                      Authorized subjects
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {teacher.subject_codes.map((c) => (
                        <Badge key={c}>{c}</Badge>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="mb-1 text-xs font-medium text-[var(--muted-foreground)]">
                      Role
                    </p>
                    <Badge
                      tone={
                        teacher.is_department_coordinator ? "accent" : "neutral"
                      }
                    >
                      {teacher.is_department_coordinator
                        ? "Department coordinator"
                        : "Subject teacher"}
                    </Badge>
                  </div>
                  <p className="border-t border-[var(--border)] pt-2 text-xs text-[var(--muted-foreground)]">
                    Attendance threshold: {teacher.attendance_threshold}%.{" "}
                    {teacher.threshold_note}
                  </p>
                </>
              ) : (
                <LoadingState />
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Demonstration system</CardTitle>
            </CardHeader>
            <CardBody>
              <p className="text-xs text-[var(--muted-foreground)]">
                Sign-in is a demo selector with no password check, and all
                student records are synthetic. Before real institutional data
                could be used, this would need genuine authentication, an audit
                trail, and a privacy review. See the project README.
              </p>
            </CardBody>
          </Card>
        </div>
      </div>
    </>
  );
}
