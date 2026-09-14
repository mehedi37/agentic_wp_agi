"use client";
import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  Action,
  Chat,
  Escalation,
  Evidence,
  Item,
  request,
  Run,
  User,
} from "@/lib/api";
import Settings from "@/components/settings";
import Assistant from "@/components/assistant";
const pages = [
  "Overview",
  "Actions",
  "Decisions",
  "Risks & issues",
  "Escalations",
  "Approvals",
  "Review queue",
  "Search",
  "Chat explorer",
  "AI assistant",
  "Ingestion",
  "Agent activity",
  "Settings",
];
const date = (v?: string | null) => (v ? new Date(v).toLocaleString() : "—");
export default function HomePage() {
  const [user, setUser] = useState<User | null>(null),
    [ready, setReady] = useState(false),
    [page, setPage] = useState("Overview");
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  const [metrics, setMetrics] = useState<Record<string, number>>({}),
    [items, setItems] = useState<Item[]>([]),
    [actions, setActions] = useState<Action[]>([]);
  const [escalations, setEscalations] = useState<Escalation[]>([]),
    [chats, setChats] = useState<Chat[]>([]),
    [runs, setRuns] = useState<Run[]>([]);
  const [results, setResults] = useState<Evidence[]>([]),
    [evidence, setEvidence] = useState<Evidence[] | null>(null),
    [query, setQuery] = useState("");
  useEffect(() => {
    if (!sessionStorage.getItem("access_token")) {
      setReady(true);
      return;
    }
    request<User>("/auth/me")
      .then(setUser)
      .catch(() => sessionStorage.removeItem("access_token"))
      .finally(() => setReady(true));
  }, []);
  const refresh = useCallback(async () => {
    if (!user) return;
    setBusy(true);
    setError("");
    try {
      if (page === "Overview") {
        const [m, e] = await Promise.all([
          request<Record<string, number>>("/dashboard/metrics"),
          request<Escalation[]>("/escalations?escalation_status=open"),
        ]);
        setMetrics(m);
        setEscalations(e);
      } else if (
        ["Actions", "Decisions", "Risks & issues", "Review queue"].includes(
          page,
        )
      ) {
        const type =
          page === "Actions"
            ? "action"
            : page === "Decisions"
              ? "decision"
              : "";
        const rows = await request<Item[]>(
          `/items${type ? `?item_type=${type}` : ""}`,
        );
        setItems(
          rows.filter((i) =>
            page === "Risks & issues"
              ? ["risk", "issue"].includes(i.type)
              : page === "Review queue"
                ? i.validation_status === "needs_review" ||
                  i.status === "needs_review"
                : true,
          ),
        );
      } else if (page === "Approvals")
        setActions(await request<Action[]>("/actions"));
      else if (page === "Escalations")
        setEscalations(await request<Escalation[]>("/escalations"));
      else if (page === "Agent activity")
        setRuns(await request<Run[]>("/agent-runs"));
      else if (["Ingestion", "Chat explorer"].includes(page))
        setChats(await request<Chat[]>("/chats"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [page, user]);
  useEffect(() => {
    setResults([]);
    setNotice("");
    void refresh();
  }, [refresh]);
  async function perform(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function login(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    await perform(async () => {
      const r = await request<User & { access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(data)),
      });
      sessionStorage.setItem("access_token", r.access_token);
      setUser(r);
    });
  }
  if (!ready) return <main className="login">Loading workspace…</main>;
  if (!user)
    return (
      <main className="login">
        <form className="login-card" onSubmit={login}>
          <div className="brand-mark">W</div>
          <p className="eyebrow">WHATSAPP INTELLIGENCE</p>
          <h1>
            Your conversations.
            <br />A clearer picture.
          </h1>
          <p className="muted">Sign in to your management workspace.</p>
          <label>
            Email
            <input
              name="email"
              type="email"
              defaultValue="manager@demo.local"
              required
              autoComplete="username"
            />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              required
              autoComplete="current-password"
            />
          </label>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <button disabled={busy}>{busy ? "Signing in…" : "Sign in →"}</button>
          <small>
            Demo: manager@demo.local or analyst@demo.local · password demo1234
          </small>
        </form>
      </main>
    );
  return (
    <div className="workspace">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">W</span>
          <div>
            Workspace<small>CONVERSATION INTELLIGENCE</small>
          </div>
        </div>
        <p className="eyebrow">MANAGEMENT</p>
        <nav aria-label="Main navigation">
          {pages.filter(name => name !== "Settings" || user.role === "manager").map((name, i) => (
            <button
              key={name}
              className={page === name ? "active" : ""}
              onClick={() => setPage(name)}
            >
              <span className="nav-number">
                {String(i + 1).padStart(2, "0")}
              </span>
              {name}
            </button>
          ))}
        </nav>
        <div className="profile">
          <strong>{user.name}</strong>
          <small>{user.role}</small>
          <button
            onClick={() => {
              sessionStorage.removeItem("access_token");
              setUser(null);
            }}
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="content">
        <header>
          <div>
            <p className="eyebrow">YOUR MANAGEMENT WORKSPACE</p>
            <h1>{page}</h1>
            <p className="muted">
              Conversations into decisions. Evidence behind every action.
            </p>
          </div>
          <button
            className="secondary"
            onClick={() => void refresh()}
            disabled={busy}
          >
            {busy ? "Loading…" : "↻ Refresh"}
          </button>
        </header>
        {error && (
          <div role="alert" className="error">
            {error}
          </div>
        )}
        {notice && (
          <div role="status" className="notice">
            {notice}
          </div>
        )}
        {page === "Overview" && (
          <>
            <section className="metrics">
              {Object.entries(metrics).map(([key, value]) => (
                <article key={key}>
                  <p>{key.replaceAll("_", " ")}</p>
                  <strong>{value}</strong>
                  <span className="metric-line" />
                </article>
              ))}
            </section>
            <section className="panel">
              <div className="section-title">
                <h2>Needs your attention</h2>
                <span className="pill">{escalations.length} open</span>
              </div>
              {escalations.length ? (
                escalations.slice(0, 8).map((e) => (
                  <div className="attention" key={e.id}>
                    <span className={`pill ${e.severity}`}>{e.severity}</span>
                    <p>{e.rationale}</p>
                  </div>
                ))
              ) : (
                <Empty text="No open escalations. Upload a chat to start collecting intelligence." />
              )}
            </section>
          </>
        )}
        {["Actions", "Decisions", "Risks & issues", "Review queue"].includes(
          page,
        ) && (
          <section className="panel">
            <div className="section-title">
              <h2>{items.length} items</h2>
              <span className="muted">
                Inspect the original source evidence
              </span>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Item</th>
                    <th>Owner</th>
                    <th>Due</th>
                    <th>Status</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((i) => (
                    <tr key={i.id}>
                      <td>
                        <span className="pill">{i.type}</span>
                        <strong>{i.title}</strong>
                      </td>
                      <td>{i.owner_raw || "Unassigned"}</td>
                      <td>{date(i.due_at)}</td>
                      <td>
                        <select
                          aria-label={`Status for ${i.title}`}
                          value={i.status}
                          disabled={busy}
                          onChange={(e) => {
                            const status = e.target.value;
                            void perform(async () => {
                              await request(`/items/${i.id}/status`, {
                                method: "PATCH",
                                body: JSON.stringify({ new_status: status }),
                              });
                              await refresh();
                            });
                          }}
                        >
                          {[
                            "open",
                            "in_progress",
                            "done",
                            "cancelled",
                            "needs_review",
                          ].map((s) => (
                            <option key={s}>{s}</option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <button
                          className="text-button"
                          onClick={() =>
                            void perform(async () =>
                              setEvidence(
                                await request<Evidence[]>(
                                  `/items/${i.id}/evidence`,
                                ),
                              ),
                            )
                          }
                        >
                          Evidence ↗
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!items.length && <Empty text="No items in this view yet." />}
          </section>
        )}
        {page === "Escalations" && (
          <section className="panel">
            {escalations.map((e) => (
              <article className="attention" key={e.id}>
                <span className={`pill ${e.severity}`}>{e.severity}</span>
                <div>
                  <h3>{e.rule.replaceAll("_", " ")}</h3>
                  <p>{e.rationale}</p>
                  <small>{e.status}</small>
                </div>
              </article>
            ))}
            {!escalations.length && <Empty text="No escalations yet." />}
          </section>
        )}
        {page === "Approvals" && (
          <section className="cards">
            {actions.map((a) => (
              <article className="panel" key={a.id}>
                <div className="section-title">
                  <span className="pill">{a.kind}</span>
                  <span className="pill">{a.status}</span>
                </div>
                <h2>{a.payload.subject || "Management action"}</h2>
                <p className="message-text">{a.payload.body}</p>
                {a.status === "pending" && user.role === "manager" && (
                  <div className="button-row">
                    <button
                      disabled={busy}
                      onClick={() =>
                        void perform(async () => {
                          await request(`/actions/${a.id}/approve`, {
                            method: "POST",
                          });
                          await refresh();
                        })
                      }
                    >
                      Approve
                    </button>
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() =>
                        void perform(async () => {
                          await request(`/actions/${a.id}/reject`, {
                            method: "POST",
                            body: JSON.stringify({
                              feedback: "Rejected from dashboard",
                            }),
                          });
                          await refresh();
                        })
                      }
                    >
                      Reject
                    </button>
                  </div>
                )}
                {user.role === "analyst" && a.status === "pending" && (
                  <small>Awaiting manager approval</small>
                )}
                {a.result != null && (
                  <pre>{JSON.stringify(a.result, null, 2)}</pre>
                )}
              </article>
            ))}
            {!actions.length && <Empty text="No proposed actions yet." />}
          </section>
        )}
        {page === "Search" && (
          <>
            <form
              className="search-bar"
              onSubmit={(e) => {
                e.preventDefault();
                void perform(async () =>
                  setResults(
                    await request<Evidence[]>(
                      `/search?q=${encodeURIComponent(query)}`,
                    ),
                  ),
                );
              }}
            >
              <input
                aria-label="Search conversations"
                placeholder="Search English, Bangla or Banglish messages…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                required
              />
              <button disabled={busy}>Search</button>
            </form>
            <Messages results={results} inspect={setEvidence} />
          </>
        )}
        {page === "Chat explorer" && (
          <>
            <select
              aria-label="Select chat"
              defaultValue=""
              onChange={(e) => {
                const id = e.target.value;
                if (id)
                  void perform(async () => {
                    const rows = await request<
                      Array<{
                        id: string;
                        text: string;
                        ts: string;
                        chat_id: string;
                      }>
                    >(`/chats/${id}/messages`);
                    setResults(rows.map((m) => ({ ...m, message_id: m.id })));
                  });
              }}
            >
              <option value="">Choose a conversation</option>
              {chats.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <Messages results={results} inspect={setEvidence} />
          </>
        )}
        {page === "Ingestion" && (
          <>
            <section className="panel">
              <h2>Import a WhatsApp chat</h2>
              <p className="muted">
                Use WhatsApp’s Export Chat feature. Android text and iOS ZIP
                exports are supported.
              </p>
              <form
                className="upload-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  const data = new FormData(e.currentTarget);
                  void perform(async () => {
                    const r = await request<{
                      inserted: number;
                      duplicates: number;
                      status: string;
                    }>("/ingest/upload", { method: "POST", body: data });
                    setNotice(
                      `${r.inserted} messages imported · ${r.duplicates} duplicates · ${r.status}`,
                    );
                  });
                }}
              >
                <label>
                  Conversation name
                  <input
                    name="chat_name"
                    required
                    placeholder="e.g. Management team"
                  />
                </label>
                <label>
                  Date order
                  <select name="date_order">
                    <option value="DMY">Day / Month / Year</option>
                    <option value="MDY">Month / Day / Year</option>
                  </select>
                </label>
                <label>
                  Export file
                  <input name="file" type="file" accept=".txt,.zip" required />
                </label>
                <button disabled={busy}>Upload and process</button>
              </form>
            </section>
            <section className="panel">
              <h2>Conversations</h2>
              {chats.map((c) => (
                <div className="section-title" key={c.id}>
                  <span>{c.name}</span>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() =>
                      void perform(async () => {
                        await request(`/chats/${c.id}/process`, {
                          method: "POST",
                        });
                        setNotice("Processing queued.");
                      })
                    }
                  >
                    Retry processing
                  </button>
                </div>
              ))}
            </section>
          </>
        )}
        {page === "Agent activity" && (
          <section className="panel">
            <h2>Execution timeline</h2>
            {runs.map((r) => (
              <article className="run" key={r.id}>
                <span className={`pill ${r.status === "failed" ? "high" : ""}`}>
                  {r.status}
                </span>
                <div>
                  <h3>
                    {r.agent} / {r.node} <small>iteration {r.iteration}</small>
                  </h3>
                  <p>{r.output_summary}</p>
                  <small>{date(r.ts)}</small>
                </div>
              </article>
            ))}
            {!runs.length && (
              <Empty text="Agent executions appear after processing a conversation." />
            )}
          </section>
        )}
        {page === "AI assistant" && <Assistant inspect={setEvidence} />}
        {page === "Settings" && user.role === "manager" && <Settings />}
        <footer>WhatsApp Intelligence · Local management workspace</footer>
      </main>
      {evidence !== null && (
        <div className="modal-backdrop" onClick={() => setEvidence(null)}>
          <section
            role="dialog"
            aria-modal="true"
            aria-label="Source evidence"
            className="evidence-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="section-title">
              <h2>Source evidence</h2>
              <button
                autoFocus
                className="secondary"
                onClick={() => setEvidence(null)}
              >
                Close
              </button>
            </div>
            {evidence.map((e) => (
              <blockquote key={e.message_id}>
                <p className="message-text">{e.text}</p>
                {e.quote && <mark>{e.quote}</mark>}
                <small>
                  {date(e.ts)} · {e.message_id}
                </small>
              </blockquote>
            ))}
            {!evidence.length && (
              <Empty text="No source evidence is attached." />
            )}
          </section>
        </div>
      )}
    </div>
  );
}
function Empty({ text }: { text: string }) {
  return <p className="empty">{text}</p>;
}
function Messages({
  results,
  inspect,
}: {
  results: Evidence[];
  inspect: (rows: Evidence[]) => void;
}) {
  return (
    <section className="panel messages">
      {results.map((m) => (
        <article key={m.message_id}>
          <p className="message-text">{m.text}</p>
          <small>{date(m.ts)}</small>
          <button className="text-button" onClick={() => inspect([m])}>
            View source ↗
          </button>
        </article>
      ))}
      {!results.length && <Empty text="No messages to display." />}
    </section>
  );
}
