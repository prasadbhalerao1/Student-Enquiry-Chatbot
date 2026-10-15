"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";

interface State<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

/**
 * Fetch a backend endpoint with loading / error / refetch handling.
 *
 * The path is the cache key: pass a fully-built path (query string included)
 * and the hook refetches whenever it changes. Pass `null` to skip fetching,
 * e.g. before a subject has been chosen.
 */
export function useApi<T>(path: string | null) {
  const [state, setState] = useState<State<T>>({
    data: null,
    loading: path !== null,
    error: null,
  });

  const load = useCallback(async () => {
    if (path === null) {
      setState({ data: null, loading: false, error: null });
      return;
    }
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await api.get<T>(path);
      setState({ data, loading: false, error: null });
    } catch (err) {
      setState({
        data: null,
        loading: false,
        error: err instanceof Error ? err.message : "Request failed.",
      });
    }
  }, [path]);

  useEffect(() => {
    // Fetching on mount is the point of this hook; the state updates happen
    // after an await, not synchronously during the effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return { ...state, reload: load };
}
