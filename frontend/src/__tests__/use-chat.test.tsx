/**
 * Tests for the streaming chat hook.
 *
 * `fetch` is stubbed with a controllable ReadableStream so SSE frames can be
 * delivered one at a time. No backend and no provider credential is involved.
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ProviderConfig } from "@/lib/types";
import { useChat } from "@/lib/use-chat";

const PROVIDER: ProviderConfig = {
  provider: "openai",
  model: "gpt-4o-mini",
  api_key: "sk-test-key",
};

function sse(event: string, data: unknown) {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

/** A fetch stub that pushes frames on demand, so streaming can be observed. */
function streamingFetch() {
  const encoder = new TextEncoder();
  let push!: (chunk: string) => void;
  let close!: () => void;

  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      push = (chunk) => controller.enqueue(encoder.encode(chunk));
      close = () => controller.close();
    },
  });

  const fetchMock = vi.fn().mockResolvedValue(
    new Response(body, {
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return { push, close, fetchMock };
}

/** A fetch stub that returns the whole stream at once. */
function completeFetch(frames: string[], status = 200) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(frames.join(""), {
      status,
      headers: { "Content-Type": "text/event-stream" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("useChat without a provider", () => {
  it("explains that no provider is configured instead of calling the API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useChat(null));
    act(() => result.current.send("Show attendance"));

    await waitFor(() => expect(result.current.messages).toHaveLength(2));
    expect(result.current.messages[1].error).toMatch(/no ai provider/i);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("useChat streaming", () => {
  it("appends each token frame as it arrives", async () => {
    const { push, close } = streamingFetch();
    const { result } = renderHook(() => useChat(PROVIDER));

    act(() => result.current.send("Summarise attendance"));
    await waitFor(() => expect(result.current.messages).toHaveLength(2));

    act(() => push(sse("token", { text: "Attendance " })));
    await waitFor(() =>
      expect(result.current.messages[1].content).toBe("Attendance "),
    );

    // The text grows progressively rather than appearing all at once.
    act(() => push(sse("token", { text: "is 77.5%." })));
    await waitFor(() =>
      expect(result.current.messages[1].content).toBe("Attendance is 77.5%."),
    );

    act(() => {
      push(sse("done", { ok: true }));
      close();
    });
    await waitFor(() => expect(result.current.isBusy).toBe(false));
  });

  it("handles a frame split across chunk boundaries", async () => {
    const { push, close } = streamingFetch();
    const { result } = renderHook(() => useChat(PROVIDER));

    act(() => result.current.send("hi"));
    await waitFor(() => expect(result.current.messages).toHaveLength(2));

    // A single SSE frame delivered in two pieces must still parse once.
    act(() => push('event: token\ndata: {"text":"par'));
    act(() => push('tial"}\n\n'));

    await waitFor(() =>
      expect(result.current.messages[1].content).toBe("partial"),
    );
    act(() => close());
  });

  it("records tool activity, including denials", async () => {
    const { push, close } = streamingFetch();
    const { result } = renderHook(() => useChat(PROVIDER));

    act(() => result.current.send("Show CB3201T"));
    await waitFor(() => expect(result.current.messages).toHaveLength(2));

    act(() =>
      push(
        sse("tool", { name: "get_subject_attendance_summary", state: "running" }),
      ),
    );
    act(() =>
      push(
        sse("tool", { name: "get_subject_attendance_summary", state: "denied" }),
      ),
    );

    await waitFor(() => {
      expect(result.current.tools).toHaveLength(1);
      expect(result.current.tools[0].state).toBe("denied");
    });
    act(() => close());
  });

  it("sends only role and content, discarding client-side fields", async () => {
    const { close, fetchMock } = streamingFetch();
    const { result } = renderHook(() => useChat(PROVIDER));

    act(() => result.current.send("question"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.messages).toEqual([{ role: "user", content: "question" }]);
    expect(body.messages[0]).not.toHaveProperty("id");
    act(() => close());
  });

  it("sends the session cookie with the request", async () => {
    const { close, fetchMock } = streamingFetch();
    const { result } = renderHook(() => useChat(PROVIDER));

    act(() => result.current.send("question"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock.mock.calls[0][1].credentials).toBe("include");
    act(() => close());
  });
});

describe("useChat error handling", () => {
  it("surfaces a provider error and produces no text", async () => {
    completeFetch([
      sse("error", { message: "The provider rejected the API key.", kind: "provider" }),
      sse("done", { ok: false }),
    ]);

    const { result } = renderHook(() => useChat(PROVIDER));
    act(() => result.current.send("question"));

    await waitFor(() => {
      expect(result.current.messages[1].error).toMatch(/rejected the API key/);
    });
    // A failed call is never replaced with invented text.
    expect(result.current.messages[1].content).toBe("");
  });

  it("reports an HTTP failure using the backend's detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Too many requests." }), {
          status: 429,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    const { result } = renderHook(() => useChat(PROVIDER));
    act(() => result.current.send("question"));

    await waitFor(() =>
      expect(result.current.messages[1].error).toBe("Too many requests."),
    );
  });

  it("reports a network failure rather than hanging", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    const { result } = renderHook(() => useChat(PROVIDER));
    act(() => result.current.send("question"));

    await waitFor(() => {
      expect(result.current.messages[1].error).toBeTruthy();
      expect(result.current.isBusy).toBe(false);
    });
  });
});

describe("useChat controls", () => {
  it("stop keeps the text already received", async () => {
    const { push } = streamingFetch();
    const { result } = renderHook(() => useChat(PROVIDER));

    act(() => result.current.send("question"));
    await waitFor(() => expect(result.current.messages).toHaveLength(2));

    act(() => push(sse("token", { text: "Partial answer" })));
    await waitFor(() =>
      expect(result.current.messages[1].content).toBe("Partial answer"),
    );

    act(() => result.current.stop());
    await waitFor(() => expect(result.current.isBusy).toBe(false));
    expect(result.current.messages[1].content).toBe("Partial answer");
  });

  it("retry re-sends the last user turn and drops the failed reply", async () => {
    completeFetch([sse("error", { message: "Upstream failed." })]);
    const { result } = renderHook(() => useChat(PROVIDER));

    act(() => result.current.send("question"));
    await waitFor(() => expect(result.current.messages[1].error).toBeTruthy());

    completeFetch([
      sse("token", { text: "Recovered." }),
      sse("done", { ok: true }),
    ]);
    act(() => result.current.retry());

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[1].content).toBe("Recovered.");
      expect(result.current.messages[1].error).toBeUndefined();
    });
  });

  it("clear empties the transcript", async () => {
    completeFetch([sse("token", { text: "hello" }), sse("done", { ok: true })]);
    const { result } = renderHook(() => useChat(PROVIDER));

    act(() => result.current.send("question"));
    await waitFor(() => expect(result.current.messages).toHaveLength(2));

    act(() => result.current.clear());
    expect(result.current.messages).toHaveLength(0);
    expect(result.current.tools).toHaveLength(0);
  });

  it("ignores an empty message and does not double-send while busy", async () => {
    const { close, fetchMock } = streamingFetch();
    const { result } = renderHook(() => useChat(PROVIDER));

    act(() => result.current.send("   "));
    expect(result.current.messages).toHaveLength(0);

    act(() => result.current.send("real question"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    // A second send while the first is still streaming must be ignored.
    act(() => result.current.send("another"));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    act(() => close());
  });

  it("keeps messages in order across turns", async () => {
    completeFetch([sse("token", { text: "first" }), sse("done", { ok: true })]);
    const { result } = renderHook(() => useChat(PROVIDER));

    act(() => result.current.send("q1"));
    await waitFor(() => expect(result.current.isBusy).toBe(false));

    completeFetch([sse("token", { text: "second" }), sse("done", { ok: true })]);
    act(() => result.current.send("q2"));

    // Wait for the second reply's text, not just for the bubble to exist.
    await waitFor(() => {
      expect(result.current.messages).toHaveLength(4);
      expect(result.current.messages[3].content).toBe("second");
    });

    expect(result.current.messages.map((m) => m.role)).toEqual([
      "user",
      "assistant",
      "user",
      "assistant",
    ]);
    expect(result.current.messages[0].content).toBe("q1");
    expect(result.current.messages[1].content).toBe("first");
    expect(result.current.messages[2].content).toBe("q2");
    expect(result.current.messages[3].content).toBe("second");
  });
});
