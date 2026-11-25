import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, token } from "./api";

export interface User { user_id: string; full_name: string; app_role: string; employee_id: string | null }

const Ctx = createContext<{ user: User | null; ready: boolean; login: (id: string, password: string) => Promise<void>; logout: () => void }>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (!token.get()) { setReady(true); return; }
    api<User>("/auth/me").then(setUser).catch(() => token.clear()).finally(() => setReady(true));
  }, []);
  const login = async (user_id: string, password: string) => {
    const r = await api<{ token: string; user: User }>("/auth/login", { json: { user_id, password } });
    token.set(r.token);
    setUser(r.user);
  };
  const logout = () => { token.clear(); setUser(null); };
  return <Ctx.Provider value={{ user, ready, login, logout }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
