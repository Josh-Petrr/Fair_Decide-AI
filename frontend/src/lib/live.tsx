import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";

export interface LiveEvent { type: string; data: any; at: number }
export interface Toast { id: number; tone: "success" | "info" | "error"; title: string; text?: string }

const Ctx = createContext<{ connected: boolean; version: number; last: LiveEvent | null; toasts: Toast[];
  notify: (t: Omit<Toast, "id">) => void; dismiss: (id: number) => void }>(null!);

/** Subscribes once to the server's event stream; every page can react to `version` / `last`. */
export function LiveProvider({ children }: { children: ReactNode }) {
  const [connected, setConnected] = useState(false);
  const [version, setVersion] = useState(0);
  const [last, setLast] = useState<LiveEvent | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seq = useRef(0);

  const notify = (t: Omit<Toast, "id">) => {
    const id = ++seq.current;
    setToasts((xs) => [...xs, { ...t, id }]);
    setTimeout(() => setToasts((xs) => xs.filter((x) => x.id !== id)), 6000);
  };
  const dismiss = (id: number) => setToasts((xs) => xs.filter((x) => x.id !== id));

  useEffect(() => {
    const es = new EventSource("/api/stream");
    es.addEventListener("hello", () => setConnected(true));
    es.onerror = () => setConnected(false);
    const handle = (type: string) => (e: MessageEvent) => {
      const data = JSON.parse(e.data || "{}");
      setLast({ type, data, at: Date.now() });
      setVersion((v) => v + 1);
      if (type === "decision" && data.decision !== "rejected")
        notify({ tone: "success", title: `${data.assignments?.length ?? 0} assignment(s) approved`, text: `by ${data.by}` });
      if (type === "decision" && data.decision === "rejected") notify({ tone: "info", title: "Recommendation rejected", text: `by ${data.by}` });
      if (type === "notification")
        notify(data.status === "sent"
          ? { tone: "success", title: "Email delivered", text: data.recipient }
          : { tone: "error", title: "Email not sent", text: data.error ?? "" });
      if (type === "reset") notify({ tone: "info", title: "Demo data reset" });
    };
    ["decision", "notification", "reset"].forEach((t) => es.addEventListener(t, handle(t)));
    return () => es.close();
  }, []);

  return <Ctx.Provider value={{ connected, version, last, toasts, notify, dismiss }}>{children}</Ctx.Provider>;
}

export const useLive = () => useContext(Ctx);
