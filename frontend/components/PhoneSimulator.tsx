"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { API, api, postJSON } from "@/lib/api";

interface OutMsg {
  to: string;
  type: "text" | "interactive";
  text?: { body: string };
  interactive?: { body: { text: string }; action: { buttons: { reply: { id: string; title: string } }[] } };
}

interface Turn {
  from: "clinic" | "family";
  phone: string;
  text: string;
  buttons?: { id: string; title: string }[];
}

const SAMPLES = [
  "இன்னைக்கு வர முடியாது, சனிக்கிழமை வரேன்",
  "ok I will come",
  "குழந்தைக்கு காய்ச்சல்",
  "wrong number",
  "STOP",
];

const VOICE_NOTES = [
  { file: "voice_reschedule_ta.wav", label: "🎤 Can't come today, Saturday" },
  { file: "voice_fever_ta.wav", label: "🎤 Baby has fever 2 days" },
  { file: "voice_confirm_ta.wav", label: "🎤 Will surely come tomorrow" },
];

/** Demo stand-in for a family's WhatsApp: shows what Thodar sent and lets you reply as the family. */
export default function PhoneSimulator({ onChange, tick }: { onChange: () => void; tick: number }) {
  const [outbox, setOutbox] = useState<OutMsg[]>([]);
  const [replies, setReplies] = useState<Turn[]>([]);
  const [phone, setPhone] = useState<string>("");
  const [text, setText] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const chatRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<OutMsg[]>("/outbox").then(setOutbox).catch(() => setOutbox([]));
  }, [tick]);

  const phones = useMemo(() => [...new Set(outbox.map((m) => m.to.slice(-10)))], [outbox]);
  const active = phone || phones[phones.length - 1] || "";

  const turns: Turn[] = useMemo(() => {
    const sent: Turn[] = outbox
      .filter((m) => m.to.endsWith(active))
      .map((m) => ({
        from: "clinic",
        phone: active,
        text: m.type === "text" ? m.text!.body : m.interactive!.body.text,
        buttons: m.interactive?.action.buttons.map((b) => b.reply),
      }));
    // Interleave family replies after the message they answered (they are appended in order).
    const mine = replies.filter((r) => r.phone === active);
    const out: Turn[] = [];
    let j = 0;
    sent.forEach((s, i) => {
      out.push(s);
      while (j < mine.length && (mine[j] as Turn & { after?: number }).after === i) out.push(mine[j++]);
    });
    return out.concat(mine.slice(j));
  }, [outbox, replies, active]);

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight });
  }, [turns.length]);

  async function send(payload: object, shown: string) {
    const after = outbox.filter((m) => m.to.endsWith(active)).length - 1;
    setReplies((r) => [...r, { from: "family", phone: active, text: shown, after } as Turn]);
    const body = { entry: [{ changes: [{ value: { messages: [{ from: `91${active}`, ...payload }] } }] }] };
    try {
      const res = await postJSON<{ handled: { intent: string; reason: string }[] }>("/webhooks/whatsapp", body);
      const h = res.handled[0];
      setStatus(h ? `Understood as “${h.intent.replace("_", " ")}” (${h.reason})` : null);
    } catch (e) {
      setStatus((e as Error).message);
    }
    onChange();
  }

  async function sendVoice(file: string, label: string) {
    const after = outbox.filter((m) => m.to.endsWith(active)).length - 1;
    setStatus("Transcribing the voice note with Saaras…");
    const blob = await (await fetch(`/samples/${file}`)).blob();
    const fd = new FormData();
    fd.append("file", blob, file);
    fd.append("phone", active);
    try {
      const res = await fetch(`${API}/demo/voice-note`, { method: "POST", body: fd });
      const h = await res.json();
      if (!res.ok) throw new Error(h.detail ?? res.statusText);
      setReplies((r) => [
        ...r,
        { from: "family", phone: active, text: `${label}\n“${h.transcript ?? "(no transcript)"}”`, after } as Turn,
      ]);
      setStatus(`Heard “${h.transcript ?? "?"}” → ${String(h.intent).replace("_", " ")} (${h.reason})`);
    } catch (e) {
      setStatus((e as Error).message);
    }
    onChange();
  }

  return (
    <aside className="phone" aria-label="Family phone simulator">
      <div className="phone-title">Family&apos;s WhatsApp · demo</div>
      {phones.length > 1 && (
        <select value={active} onChange={(e) => setPhone(e.target.value)} style={{ marginTop: 8 }}>
          {phones.map((p) => (
            <option key={p} value={p}>
              +91 {p}
            </option>
          ))}
        </select>
      )}
      <div className="chat" ref={chatRef}>
        {turns.length === 0 && (
          <p className="hint">No messages yet. Press “Send today&apos;s WhatsApp reminders”, then reply here as the family.</p>
        )}
        {turns.map((t, i) => (
          <div key={i} className={`bubble ${t.from === "family" ? "me" : ""}`}>
            <div className="to">{t.from === "clinic" ? "Thodar" : "Family"}</div>
            {t.text}
            {t.buttons && (
              <div className="chip-row">
                {t.buttons.map((b) => (
                  <button
                    key={b.id}
                    className="chip"
                    onClick={() => send({ type: "interactive", interactive: { type: "button_reply", button_reply: b } }, b.title)}
                  >
                    {b.title}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      {active && (
        <>
          <form
            className="row"
            onSubmit={(e) => {
              e.preventDefault();
              if (text.trim()) send({ type: "text", text: { body: text } }, text);
              setText("");
            }}
          >
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Reply as the family…" />
            <button className="btn small accent">Send</button>
          </form>
          <div className="chip-row">
            {VOICE_NOTES.map((v) => (
              <button key={v.file} className="chip" onClick={() => sendVoice(v.file, v.label)}>
                {v.label}
              </button>
            ))}
          </div>
          <div className="chip-row">
            {SAMPLES.map((s) => (
              <button key={s} className="chip" onClick={() => send({ type: "text", text: { body: s } }, s)}>
                {s}
              </button>
            ))}
          </div>
        </>
      )}
      {status && <p className="hint">{status}</p>}
    </aside>
  );
}
