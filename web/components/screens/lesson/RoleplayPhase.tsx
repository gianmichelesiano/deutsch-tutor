"use client";

import { useEffect, useRef, useState } from "react";
import { api, type LessonDetail } from "@/lib/api";
import { LoadingDots } from "@/components/ui";

export function RoleplayPhase({ lesson, onUpdated }: { lesson: LessonDetail; onUpdated: (l: LessonDetail) => void }) {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const send = (override?: string) => {
    const content = (override ?? input).trim();
    if (!content || sending || lesson.dialogue_closed) return;
    setSending(true);
    setInput("");
    api
      .roleplayMessage(lesson.id, content)
      .then((res) => {
        onUpdated({
          ...lesson,
          roleplay_messages: [
            ...lesson.roleplay_messages,
            { role: "user", content, requested_words: res.requested_words },
            { role: "agent", content: res.agent_text },
          ],
          dialogue_closed: res.dialogue_closed,
        });
      })
      .catch(() => setSending(false))
      .finally(() => setSending(false));
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lesson.roleplay_messages.length, sending]);

  return (
    <div>
      <div className="font-serif text-xl font-semibold">Rollenspiel</div>
      <div className="mb-4 text-[13px] text-muted">Gioco di ruolo · {lesson.role_label ?? "Gesprächspartner"}</div>
      <div className="flex flex-col gap-2.5">
        {lesson.roleplay_messages.map((m, i) => {
          const isUser = m.role === "user";
          const hasReq = (m.requested_words?.length ?? 0) > 0;
          return (
            <div key={i} className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}>
              {isUser && hasReq && (
                <div className="mb-1 rounded-md bg-vocab-new-bg px-1.5 py-0.5 text-[10px] font-semibold text-vocab-new">
                  Parola richiesta con [ ]
                </div>
              )}
              <div
                className={`max-w-[80%] rounded-[14px] px-3.5 py-2.5 text-sm ${
                  isUser ? "bg-accent text-surface" : "bg-card text-primary"
                }`}
              >
                {m.content}
              </div>
            </div>
          );
        })}
        {sending && (
          <div className="flex items-start">
            <div className="rounded-[14px] bg-card px-3.5 py-2.5 text-sm text-primary">
              <LoadingDots inline />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      {!lesson.dialogue_closed && (
        <div className="mt-4 flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send(e.currentTarget.value)}
            placeholder="Scrivi in tedesco. Usa [parola] se ti manca..."
            className="flex-1 rounded-btn border border-border bg-card px-3.5 py-3 text-sm"
          />
          <button onClick={() => send(input)} disabled={sending} className="rounded-btn bg-accent px-4 font-semibold text-surface disabled:opacity-40">
            →
          </button>
        </div>
      )}
    </div>
  );
}
