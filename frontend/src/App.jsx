import { useEffect, useRef, useState } from "react";
import { ThinkingOrb } from "thinking-orbs";

const CHIPS = ["What time is check-in?", "Is breakfast included?", "Do you have a pool?", "What's the cancellation policy?"];
const WELCOME = { id: 0, role: "assistant", text: "Welcome to Lakeview Grand. Ask me anything about the hotel, or check room availability." };

const today = () => new Date().toLocaleDateString("en-CA"); // local YYYY-MM-DD
const fmt = (iso) => new Date(iso + "T00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

async function post(path, body) {
  let res;
  try {
    res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  } catch {
    throw new Error("Can't reach the server. Check your connection and try again.");
  }
  if (!res.ok) {
    throw new Error(res.status === 422 ? "That request wasn't valid. Please check your input." : "Something went wrong on our side. Please try again.");
  }
  return res.json();
}

// The model replies with **bold**; render it without innerHTML.
const Text = ({ children }) => children.split(/\*\*(.+?)\*\*/g).map((p, i) => (i % 2 ? <strong key={i}>{p}</strong> : p));

function Rooms({ a }) {
  return (
    <section className="rooms" aria-label="Available rooms">
      <p className="dates">{fmt(a.check_in)} – {fmt(a.check_out)} · {plural(a.nights, "night")} · {plural(a.adults, "guest")}</p>
      <ul>
        {a.rooms.map((r) => (
          <li key={r.id}>
            <h3>{r.name}</h3>
            <p>Sleeps {r.capacity}</p>
            <p className="price">${r.price_per_night}<span> / night</span></p>
            <p className="total">${r.total} total</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Message({ m }) {
  return (
    <div className={`row ${m.role}`}>
      <div className="bubble"><Text>{m.text}</Text></div>
      {m.degraded && <small className="note">Limited mode: the AI assistant is unavailable, so this answer comes from basic FAQ matching.</small>}
      {m.availability?.rooms.length > 0 && <Rooms a={m.availability} />}
    </div>
  );
}

function AvailabilityForm({ onSubmit, onCancel }) {
  const [checkIn, setCheckIn] = useState("");
  const [checkOut, setCheckOut] = useState("");
  const [adults, setAdults] = useState(2);
  const [error, setError] = useState("");
  const first = useRef(null);
  useEffect(() => first.current?.focus(), []);

  function submit(e) {
    e.preventDefault();
    if (checkOut <= checkIn) return setError("Check-out must be after check-in.");
    onSubmit({ checkIn, checkOut, adults });
  }

  return (
    <form className="avail" onSubmit={submit} aria-label="Check availability">
      <div className="fields">
        <label>Check-in
          <input ref={first} type="date" required min={today()} value={checkIn} onChange={(e) => { setCheckIn(e.target.value); setError(""); }} />
        </label>
        <label>Check-out
          <input type="date" required min={checkIn || today()} value={checkOut} onChange={(e) => { setCheckOut(e.target.value); setError(""); }} />
        </label>
        <label>Guests
          <input type="number" required min="1" max="10" value={adults} onChange={(e) => setAdults(Number(e.target.value))} />
        </label>
      </div>
      {error && <p role="alert" className="field-error">{error}</p>}
      <div className="actions">
        <button type="submit">Search rooms</button>
        <button type="button" className="ghost" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

export default function App() {
  const [messages, setMessages] = useState([WELCOME]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [text, setText] = useState("");
  const end = useRef(null);
  useEffect(() => end.current?.scrollIntoView?.({ behavior: "smooth" }), [messages, loading, error, formOpen]);

  // Every request goes through run(): one place for loading, errors and retry.
  async function run(msgs, fetcher) {
    setMessages(msgs);
    setError(null);
    setLoading(true);
    try {
      const m = await fetcher();
      setMessages([...msgs, { id: Date.now(), role: "assistant", ...m }]);
      if (m.type === "needs_availability_input") setFormOpen(true);
    } catch (e) {
      setError({ msg: e.message, retry: () => run(msgs, fetcher) });
    } finally {
      setLoading(false);
    }
  }

  function ask(question) {
    if (loading || !question.trim()) return;
    const msgs = [...messages, { id: Date.now(), role: "user", text: question.trim() }];
    setText("");
    setFormOpen(false);
    run(msgs, async () => {
      const history = msgs.slice(1).slice(-20).map(({ role, text }) => ({ role, content: text }));
      const r = await post("/api/chat", { messages: history });
      return { text: r.reply, type: r.type, availability: r.availability, degraded: r.degraded };
    });
  }

  function check({ checkIn, checkOut, adults }) {
    const summary = `Availability: ${fmt(checkIn)} to ${fmt(checkOut)}, ${plural(adults, "guest")}`;
    const msgs = [...messages, { id: Date.now(), role: "user", text: summary }];
    setFormOpen(false);
    run(msgs, async () => {
      const a = await post("/api/availability", { check_in: checkIn, check_out: checkOut, adults });
      const n = a.rooms.length;
      return {
        text: n ? `${plural(n, "room type")} available for ${plural(a.nights, "night")}.` : "Sorry, no rooms are available for those dates and party size.",
        type: "availability",
        availability: a,
      };
    });
  }

  return (
    <div className="app">
      <header>
        <h1>Lakeview Grand</h1>
        <p>Guest assistant</p>
      </header>

      <main role="log" aria-label="Conversation" aria-live="polite">
        {messages.map((m) => <Message key={m.id} m={m} />)}
        {messages.length === 1 && (
          <div className="chips">
            {CHIPS.map((c) => <button key={c} type="button" onClick={() => ask(c)}>{c}</button>)}
          </div>
        )}
        {loading && <div className="row assistant"><div className="bubble typing" role="status" aria-label="Assistant is typing"><ThinkingOrb state="searching" size={20} theme="light" /></div></div>}
        {error && (
          <div className="row assistant">
            <div className="bubble error" role="alert">{error.msg} <button type="button" onClick={error.retry}>Try again</button></div>
          </div>
        )}
        {formOpen && <AvailabilityForm onSubmit={check} onCancel={() => setFormOpen(false)} />}
        <div ref={end} />
      </main>

      <form className="composer" onSubmit={(e) => { e.preventDefault(); ask(text); }}>
        <button type="button" className="pill" aria-expanded={formOpen} onClick={() => setFormOpen((o) => !o)}>
          Check availability
        </button>
        <div className="line">
          <label htmlFor="q" className="sr">Your question</label>
          <input id="q" value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask about rooms, policies, amenities…" maxLength={2000} autoComplete="off" />
          <button type="submit" disabled={loading || !text.trim()}>Send</button>
        </div>
      </form>
    </div>
  );
}
