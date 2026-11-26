"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, guestStore, refreshSession, setAccessToken, type User } from "@/lib/api";

type AuthState = {
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (email: string, password: string, locale: string) => Promise<User>;
  logout: () => Promise<void>;
  setUser: (u: User | null) => void;
};

const AuthContext = createContext<AuthState | null>(null);

/** Attach the guest session the user just completed, so it is kept beyond 24h. */
async function claimGuestSession() {
  const latest = guestStore.latestSession();
  if (!latest) return;
  try {
    await api.claim(latest.id, latest.token);
  } catch {
    /* already claimed or expired */
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    refreshSession().then((u) => {
      setUser(u);
      setReady(true);
    });
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const out = await api.login(email, password);
    setAccessToken(out.access_token);
    await claimGuestSession();
    setUser(out.user);
    return out.user;
  }, []);

  const register = useCallback(async (email: string, password: string, locale: string) => {
    const out = await api.register(email, password, locale);
    setAccessToken(out.access_token);
    await claimGuestSession();
    setUser(out.user);
    return out.user;
  }, []);

  const logout = useCallback(async () => {
    await api.logout().catch(() => undefined);
    setAccessToken(null);
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, ready, login, register, logout, setUser }), [user, ready, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
