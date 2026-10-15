"use client";

import {
  AlertCircle,
  Check,
  Copy,
  MessageSquare,
  RotateCcw,
  Send,
  Settings as SettingsIcon,
  Square,
  Trash2,
  Wrench,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { PageHeader } from "@/components/app-shell";
import { useSession } from "@/components/session-provider";
import {
  Badge,
  Button,
  Card,
  LoadingState,
} from "@/components/ui/primitives";
import type { ChatMessage } from "@/lib/types";
import { useChat } from "@/lib/use-chat";

const SUGGESTIONS = [
  "Show attendance below 75% in Machine Learning.",
  "Summarize attendance across my assigned subjects.",
  "Which students have the lowest attendance in CB3201T?",
  "Show academic performance for my Robotics Lab.",
  "Find students with overdue assignments.",
  "Summarize extracurricular participation for my class.",
  "Create a concise attendance report for this subject.",
];

export default function AssistantPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <AssistantView />
    </Suspense>
  );
}

function AssistantView() {
  const { teacher, provider } = useSession();
  const params = useSearchParams();
  const { messages, status, isBusy, tools, send, stop, retry, clear } =
    useChat(provider);

  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const prefilled = useRef(false);

  // Accept a question handed over from a dashboard quick action.
  useEffect(() => {
    const q = params.get("q");
    if (q && !prefilled.current) {
      prefilled.current = true;
      setInput(q);
      textareaRef.current?.focus();
    }
  }, [params]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, status]);

  function submit() {
    if (!input.trim() || isBusy) return;
    send(input);
    setInput("");
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter inserts a newline.
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="flex h-[calc(100vh-7.5rem)] flex-col">
      <PageHeader
        title="AI Assistant"
        description="Answers come from authorized database queries. The assistant can only read records for the subjects you teach."
        actions={
          messages.length > 0 ? (
            <Button variant="outline" size="sm" onClick={clear}>
              <Trash2 className="h-3.5 w-3.5" />
              Clear
            </Button>
          ) : null
        }
      />

      {/* Provider status */}
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
        {provider ? (
          <>
            <Badge tone="success">
              <Check className="h-3 w-3" />
              {provider.provider} · {provider.model}
            </Badge>
            <span className="text-[var(--muted-foreground)]">
              Your API key stays in this browser tab and is sent only with each
              request.
            </span>
          </>
        ) : (
          <>
            <Badge tone="warning">
              <AlertCircle className="h-3 w-3" />
              No provider configured
            </Badge>
            <Link
              href="/settings"
              className="inline-flex items-center gap-1 font-medium text-[var(--accent)] underline"
            >
              <SettingsIcon className="h-3 w-3" />
              Configure one in Settings
            </Link>
          </>
        )}
      </div>

      {/* Transcript */}
      <Card className="flex min-h-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {messages.length === 0 ? (
            <EmptyChat
              teacherName={teacher?.full_name ?? "there"}
              onPick={(q) => {
                setInput(q);
                textareaRef.current?.focus();
              }}
            />
          ) : (
            <div className="space-y-4">
              {messages.map((m) => (
                <Bubble key={m.id} message={m} onRetry={retry} busy={isBusy} />
              ))}

              {isBusy && (
                <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
                  <span
                    className="h-2 w-2 animate-pulse rounded-full bg-[var(--accent)]"
                    aria-hidden
                  />
                  <span role="status">
                    {status === "thinking"
                      ? "Looking up authorized records…"
                      : "Generating response…"}
                  </span>
                </div>
              )}

              {tools.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {tools.map((t) => (
                    <Badge
                      key={t.name}
                      tone={t.state === "denied" ? "danger" : "neutral"}
                    >
                      <Wrench className="h-3 w-3" />
                      {t.name}
                      {t.state === "denied" && " (denied)"}
                    </Badge>
                  ))}
                </div>
              )}

              <div ref={endRef} />
            </div>
          )}
        </div>

        {/* Composer */}
        <div className="border-t border-[var(--border)] p-3">
          <div className="flex gap-2">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={2}
              placeholder="Ask about attendance, marks, assignments or activities…"
              aria-label="Message"
              className="min-h-[2.75rem] flex-1 resize-y rounded-md border border-[var(--border-strong)] bg-[var(--surface)] px-3 py-2 text-sm placeholder:text-[var(--muted-foreground)]"
            />
            <div className="flex flex-col gap-2">
              {isBusy ? (
                <Button variant="danger" onClick={stop} title="Stop generating">
                  <Square className="h-3.5 w-3.5" />
                  Stop
                </Button>
              ) : (
                <Button onClick={submit} disabled={!input.trim()}>
                  <Send className="h-3.5 w-3.5" />
                  Send
                </Button>
              )}
            </div>
          </div>
          <p className="mt-1.5 text-xs text-[var(--muted-foreground)]">
            Enter to send · Shift+Enter for a new line
          </p>
        </div>
      </Card>
    </div>
  );
}

function EmptyChat({
  teacherName,
  onPick,
}: {
  teacherName: string;
  onPick: (q: string) => void;
}) {
  return (
    <div className="mx-auto max-w-2xl py-6">
      <div className="mb-5 flex items-center gap-2.5">
        <MessageSquare className="h-6 w-6 text-[var(--accent)]" />
        <div>
          <h2 className="font-semibold">Hello, {teacherName}</h2>
          <p className="text-sm text-[var(--muted-foreground)]">
            Ask about your students. Every answer is built from database records
            inside your teaching scope.
          </p>
        </div>
      </div>

      <p className="mb-2 text-xs font-medium text-[var(--muted-foreground)]">
        Suggested questions
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onPick(s)}
            className="rounded-md border border-[var(--border)] px-3 py-2 text-left text-sm transition-colors hover:border-[var(--accent)] hover:bg-[var(--accent-soft)]"
          >
            {s}
          </button>
        ))}
      </div>

      <p className="mt-5 rounded-md bg-[var(--surface-muted)] p-3 text-xs text-[var(--muted-foreground)]">
        The assistant cannot write to records, run SQL, or read subjects taught
        by other faculty. Requests outside your scope are refused by the
        backend, not just by the model.
      </p>
    </div>
  );
}

function Bubble({
  message,
  onRetry,
  busy,
}: {
  message: ChatMessage;
  onRetry: () => void;
  busy: boolean;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable; nothing useful to show */
    }
  }

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-lg bg-[var(--accent)] px-3.5 py-2 text-sm text-[var(--accent-foreground)]">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="group">
      {message.content && (
        <div className="md-body max-w-none rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3.5 py-2.5">
          <Markdown remarkPlugins={[remarkGfm]}>{message.content}</Markdown>
        </div>
      )}

      {message.error && (
        <div
          role="alert"
          className="rounded-lg border border-[var(--danger)] bg-[var(--danger-soft)] px-3.5 py-2.5 text-sm"
        >
          <p className="flex items-center gap-1.5 font-medium text-[var(--danger)]">
            <AlertCircle className="h-4 w-4" />
            The request failed
          </p>
          <p className="mt-1">{message.error}</p>
          <Button
            variant="outline"
            size="sm"
            className="mt-2"
            onClick={onRetry}
            disabled={busy}
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Retry
          </Button>
        </div>
      )}

      {message.content && !message.error && (
        <div className="mt-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
          <Button variant="ghost" size="sm" onClick={copy}>
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5" />
                Copied
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" />
                Copy
              </>
            )}
          </Button>
        </div>
      )}
    </div>
  );
}
