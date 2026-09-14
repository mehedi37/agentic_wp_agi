"use client";
import { FormEvent, useState } from "react";
import { Evidence, request } from "@/lib/api";

export default function Assistant({
  inspect,
}: {
  inspect: (rows: Evidence[]) => void;
}) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<Evidence[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function ask(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await request<{ answer: string; citations: Evidence[] }>(
        "/assistant/chat",
        {
          method: "POST",
          body: JSON.stringify({ question }),
        },
      );
      setAnswer(result.answer);
      setCitations(result.citations);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <h2>Ask your management assistant</h2>
      <p className="muted">
        Find answers with links to the original conversations.
      </p>
      <div className="button-row">
        {[
          "What is overdue and who owns it?",
          "What are the main risks?",
          "Summarize recent decisions",
        ].map((q) => (
          <button key={q} className="secondary" onClick={() => setQuestion(q)}>
            {q}
          </button>
        ))}
      </div>
      <form className="search-bar" style={{ marginTop: 24 }} onSubmit={ask}>
        <input
          aria-label="Assistant question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a management question…"
          required
          maxLength={4000}
        />
        <button disabled={busy}>{busy ? "Checking sources…" : "Ask"}</button>
      </form>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {answer && <div className="message-text">{answer}</div>}
      {citations.length > 0 && (
        <div className="button-row">
          {citations.map((c, i) => (
            <button
              key={c.message_id}
              className="secondary"
              onClick={() => inspect([c])}
            >
              Source {i + 1} ↗
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
