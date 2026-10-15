"use client";

import { useCallback, useRef, useState } from "react";

import { API_BASE } from "@/lib/api";
import type { ChatMessage, ProviderConfig } from "@/lib/types";

type Status = "idle" | "thinking" | "streaming";

let idCounter = 0;
const nextId = () => `m${++idCounter}-${Date.now()}`;

/**
 * Chat state backed by the backend's SSE stream.
 *
 * Tokens are appended as each `token` frame arrives, so text appears at the
 * pace the provider generates it. Nothing is simulated with timers.
 */
export function useChat(provider: ProviderConfig | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [tools, setTools] = useState<{ name: string; state: string }[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  const isBusy = status !== "idle";

  const run = useCallback(
    async (history: ChatMessage[]) => {
      if (!provider) {
        setMessages((m) => [
          ...m,
          {
            id: nextId(),
            role: "assistant",
            content: "",
            error:
              "No AI provider is configured. Open Settings to choose a provider and enter your API key.",
          },
        ]);
        return;
      }

      const controller = new AbortController();
      abortRef.current = controller;
      setStatus("thinking");
      setTools([]);

      const assistantId = nextId();
      setMessages((m) => [
        ...m,
        { id: assistantId, role: "assistant", content: "" },
      ]);

      const patch = (fn: (msg: ChatMessage) => ChatMessage) =>
        setMessages((m) => m.map((x) => (x.id === assistantId ? fn(x) : x)));

      try {
        const res = await fetch(`${API_BASE}/api/chat`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify({
            messages: history
              .filter((m) => !m.error && m.content.trim())
              .map((m) => ({ role: m.role, content: m.content })),
            provider,
          }),
        });

        if (!res.ok) {
          let detail = `The request failed (${res.status}).`;
          try {
            const body = await res.json();
            if (typeof body?.detail === "string") detail = body.detail;
          } catch {
            /* keep the generic message */
          }
          patch((m) => ({ ...m, error: detail }));
          return;
        }

        if (!res.body) {
          patch((m) => ({ ...m, error: "The response stream was empty." }));
          return;
        }

        // Parse the SSE frames as they arrive.
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split("\n\n");
          buffer = frames.pop() ?? "";

          for (const frame of frames) {
            let event = "message";
            let data = "";
            for (const line of frame.split("\n")) {
              if (line.startsWith("event:")) event = line.slice(6).trim();
              else if (line.startsWith("data:")) data += line.slice(5).trim();
            }
            if (!data) continue;

            let payload: Record<string, unknown>;
            try {
              payload = JSON.parse(data);
            } catch {
              continue;
            }

            if (event === "token" && typeof payload.text === "string") {
              const text = payload.text;
              setStatus("streaming");
              patch((m) => ({ ...m, content: m.content + text }));
            } else if (event === "status") {
              if (payload.state === "streaming") setStatus("streaming");
            } else if (event === "tool") {
              setTools((t) => {
                const name = String(payload.name);
                const state = String(payload.state);
                const existing = t.findIndex((x) => x.name === name);
                if (existing >= 0) {
                  const copy = [...t];
                  copy[existing] = { name, state };
                  return copy;
                }
                return [...t, { name, state }];
              });
            } else if (event === "error") {
              patch((m) => ({
                ...m,
                error:
                  typeof payload.message === "string"
                    ? payload.message
                    : "The request failed.",
              }));
            }
          }
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          // Stopped by the teacher. Keep whatever text already arrived.
          patch((m) =>
            m.content.trim()
              ? m
              : { ...m, error: "Generation stopped before any text arrived." },
          );
        } else {
          patch((m) => ({
            ...m,
            error:
              err instanceof Error
                ? err.message
                : "Could not reach the backend.",
          }));
        }
      } finally {
        abortRef.current = null;
        setStatus("idle");
        // Drop any empty assistant bubble that produced neither text nor error.
        setMessages((m) =>
          m.filter((x) => x.content.trim() !== "" || x.error || x.role === "user"),
        );
      }
    },
    [provider],
  );

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isBusy) return;
      const userMsg: ChatMessage = {
        id: nextId(),
        role: "user",
        content: trimmed,
      };
      setMessages((m) => {
        const next = [...m, userMsg];
        void run(next);
        return next;
      });
    },
    [isBusy, run],
  );

  /** Re-run the last user turn, discarding the failed assistant reply. */
  const retry = useCallback(() => {
    if (isBusy) return;
    setMessages((m) => {
      const lastUser = [...m].reverse().find((x) => x.role === "user");
      if (!lastUser) return m;
      const idx = m.findIndex((x) => x.id === lastUser.id);
      const next = m.slice(0, idx + 1);
      void run(next);
      return next;
    });
  }, [isBusy, run]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const clear = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setTools([]);
    setStatus("idle");
  }, []);

  return { messages, status, isBusy, tools, send, stop, retry, clear };
}
