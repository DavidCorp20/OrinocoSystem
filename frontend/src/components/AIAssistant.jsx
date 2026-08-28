import { useEffect, useRef, useState } from "react";
import { Bot, Send, X, Sparkles } from "lucide-react";
import api, { streamChat } from "../lib/api";

const QUICK_PROMPTS = [
  "¿Qué productos debo comprar hoy?",
  "¿Cuál es mi producto con mayor ganancia?",
  "¿Cómo van mis ventas comparadas con el mes pasado?",
  "¿Qué productos están por agotarse?",
];

const renderMd = (text) =>
  text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : part
  );

export default function AIAssistant({ open, onClose }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    if (open) {
      api.get("/assistant/history").then((r) => setMessages(r.data.messages || [])).catch(() => {});
    }
  }, [open]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  const send = async (text) => {
    const msg = (text ?? input).trim();
    if (!msg || sending) return;
    setInput("");
    setSending(true);
    setMessages((m) => [...m, { role: "user", content: msg }, { role: "assistant", content: "", pending: true }]);
    try {
      await streamChat(msg, (token) => {
        setMessages((m) => {
          const copy = [...m];
          const last = copy[copy.length - 1];
          copy[copy.length - 1] = { ...last, content: last.content + token, pending: false };
          return copy;
        });
      });
    } catch {
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: "No pude conectar con el asistente. Intenta de nuevo." };
        return copy;
      });
    } finally {
      setSending(false);
    }
  };

  if (!open) return null;

  return (
    <div
      data-testid="ai-assistant-panel"
      className="fixed bottom-4 right-4 z-50 w-[calc(100vw-2rem)] sm:w-96 h-[70vh] sm:h-[560px] bg-card border border-border rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-rise"
    >
      <div className="bg-primary text-white px-4 py-3 flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-full bg-white/15 flex items-center justify-center">
          <Bot className="w-4 h-4" />
        </div>
        <div className="flex-1">
          <p className="font-heading font-bold text-sm leading-tight">Pyme, tu asesor</p>
          <p className="text-[11px] text-white/70">Responde solo con los datos de tu negocio</p>
        </div>
        <button data-testid="ai-assistant-close-btn" onClick={onClose} className="p-1.5 rounded-lg hover:bg-white/15 transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="space-y-3">
            <div className="flex items-start gap-2">
              <Sparkles className="w-4 h-4 text-accent mt-1 shrink-0" />
              <p className="text-sm text-slate-600">
                Hola, soy <b>Pyme</b>. Conozco tus ventas, tu inventario y tus gastos. Pregúntame lo que quieras saber de tu negocio.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {QUICK_PROMPTS.map((q) => (
                <button
                  key={q}
                  data-testid={`ai-quick-prompt-${q.slice(0, 12).replace(/\W/g, "-")}`}
                  onClick={() => send(q)}
                  className="text-xs bg-secondary hover:bg-primary hover:text-white text-slate-700 px-3 py-1.5 rounded-full border border-border transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              data-testid={`ai-message-${m.role}-${i}`}
              className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                m.role === "user" ? "bg-primary text-white rounded-br-md" : "bg-secondary text-slate-700 rounded-bl-md"
              }`}
            >
              {renderMd(m.content)}
              {m.pending && !m.content && (
                <span className="flex gap-1 py-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-400 typing-dot" />
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-400 typing-dot" style={{ animationDelay: "0.2s" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-400 typing-dot" style={{ animationDelay: "0.4s" }} />
                </span>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-border p-3 flex gap-2">
        <input
          data-testid="ai-chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Pregunta sobre tu negocio…"
          className="flex-1 text-sm bg-secondary rounded-xl px-3.5 py-2.5 outline-none focus:ring-2 focus:ring-primary/40"
        />
        <button
          data-testid="ai-chat-send-button"
          onClick={() => send()}
          disabled={sending || !input.trim()}
          className="w-10 h-10 rounded-xl bg-primary text-white flex items-center justify-center hover:bg-primary/90 disabled:opacity-40 transition-colors"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
