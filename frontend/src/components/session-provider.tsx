"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { ApiError, api } from "@/lib/api";
import type { ProviderConfig, TeacherProfile } from "@/lib/types";

interface SessionValue {
  teacher: TeacherProfile | null;
  loading: boolean;
  error: string | null;
  signIn: (teacherId: string) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;

  /**
   * BYOK provider settings.
   *
   * Held in React state only -- never localStorage, never a cookie, never a
   * URL. Reloading the page clears the key, which is the intended trade-off.
   */
  provider: ProviderConfig | null;
  setProvider: (config: ProviderConfig | null) => void;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [teacher, setTeacher] = useState<TeacherProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState<ProviderConfig | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setTeacher(await api.get<TeacherProfile>("/api/teachers/me"));
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthenticated) {
        setTeacher(null); // simply not signed in yet
      } else {
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Restoring an existing session on mount requires a round trip; the state
    // updates happen after an await, not synchronously during the effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  const signIn = useCallback(async (teacherId: string) => {
    setError(null);
    const profile = await api.post<TeacherProfile>("/api/demo-session", {
      teacher_id: teacherId,
    });
    setTeacher(profile);
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.post("/api/auth/logout");
    } finally {
      setTeacher(null);
      // Drop the in-memory credential along with the session.
      setProvider(null);
    }
  }, []);

  return (
    <SessionContext.Provider
      value={{
        teacher,
        loading,
        error,
        signIn,
        signOut,
        refresh,
        provider,
        setProvider,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}
