"use client";
import { useEffect, useState } from "react";
import { request } from "@/lib/api";

type Rule = { key: string; enabled: boolean; params: Record<string, number> };
export default function Settings() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    request<Rule[]>("/settings/rules").then(setRules).catch(e => setNotice(e.message));
  }, []);
  return <section className="panel"><h2>Monitor rules</h2>
    <p className="muted">Changes apply to the next processing batch or scheduled monitor cycle.</p>
    {notice && <p role="status">{notice}</p>}
    {rules.map((rule, index) => <form key={rule.key} className="upload-form" onSubmit={async event => {
      event.preventDefault(); setBusy(true); setNotice("");
      try {
        await request(`/settings/rules/${rule.key}`, { method: "PUT", body: JSON.stringify({ enabled: rule.enabled, params: rule.params }) });
        setNotice("Rule saved.");
      } catch(e) { setNotice((e as Error).message); }
      finally { setBusy(false); }
    }}><h3>{rule.key.replaceAll("_", " ")}</h3>
      <label><input type="checkbox" checked={rule.enabled} onChange={event => setRules(current => current.map((r, i) => i === index ? { ...r, enabled: event.target.checked } : r))} /> Enabled</label>
      {Object.entries(rule.params).map(([key, value]) => <label key={key}>{key.replaceAll("_", " ")}
        <input type="number" min={1} max={365} required value={value} onChange={event => setRules(current => current.map((r, i) => i === index ? { ...r, params: { ...r.params, [key]: Number(event.target.value) } } : r))} />
      </label>)}<button disabled={busy}>Save rule</button>
    </form>)}
  </section>;
}
