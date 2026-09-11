"use client";

import { useEffect, useState } from "react";
import { api, type LessonDetail, type WarmupWord } from "@/lib/api";

interface WarmupState {
  sending: boolean;
  sentence?: string;
  is_correct?: boolean;
  feedback?: string;
  corrected_sentence?: string | null;
}

export function WarmupPhase({ lesson, onAnswered }: { lesson: LessonDetail; onAnswered: (n: number) => void }) {
  const words = lesson.warmup_words ?? [];
  const [states, setStates] = useState<Record<number, WarmupState>>({});
  const [texts, setTexts] = useState<Record<number, string>>({});

  useEffect(() => {
    onAnswered(Object.values(states).filter((s) => s.feedback !== undefined).length);
  }, [states, onAnswered]);

  const submit = (w: WarmupWord, sentenceOverride?: string) => {
    const sentence = (sentenceOverride ?? texts[w.vocab_item_id] ?? "").trim();
    if (!sentence) return;
    setStates((s) => ({ ...s, [w.vocab_item_id]: { sending: true, sentence } }));
    api
      .warmupAnswer(lesson.id, w.vocab_item_id, sentence)
      .then((res) =>
        setStates((s) => ({
          ...s,
          [w.vocab_item_id]: {
            sending: false,
            sentence,
            is_correct: res.is_correct,
            feedback: res.feedback_it,
            corrected_sentence: res.corrected_sentence,
          },
        })),
      )
      .catch(() => setStates((s) => ({ ...s, [w.vocab_item_id]: { sending: false, sentence, is_correct: false, feedback: "Errore, riprova." } })));
  };

  return (
    <div>
      <div className="font-serif text-xl font-semibold">Aufwärmen</div>
      <div className="mb-4 text-[13px] text-muted">Riscaldamento · scrivi una frase per ogni parola</div>
      {words.map((w) => {
        const st = states[w.vocab_item_id];
        return (
          <div key={w.vocab_item_id} className="mb-2.5 rounded-[14px] border border-border bg-card p-3.5">
            <div className="mb-2 flex items-center justify-between">
              <div>
                <span className="font-serif text-base font-semibold">{w.de}</span>
                <span className="ml-2 text-[13px] text-muted">{w.it}</span>
              </div>
              <span className={`rounded-lg px-2 py-0.5 text-[11px] font-semibold ${w.is_new ? "bg-vocab-new-bg text-vocab-new" : "bg-vocab-seen-bg text-vocab-seen"}`}>
                {w.is_new ? "Nuova" : "Ripasso"}
              </span>
            </div>
            {st?.feedback ? (
              <div>
                <div className="mb-1.5 rounded-lg border border-border bg-[#FBF8F2] px-2.5 py-1.5 text-sm">
                  <span className="mr-1.5 text-[11px] uppercase tracking-wide text-muted">Tu</span>
                  <span className={st.corrected_sentence ? "line-through decoration-src-error/60" : ""}>{st.sentence}</span>
                  {!st.is_correct && st.corrected_sentence && (
                    <span className="ml-2 font-semibold text-vocab-used">{st.corrected_sentence}</span>
                  )}
                </div>
                <div
                  className={`rounded-lg px-2.5 py-1.5 text-xs ${
                    st.is_correct ? "bg-vocab-used-bg text-vocab-used" : "bg-src-error-bg text-src-error"
                  }`}
                >
                  {st.feedback}
                </div>
              </div>
            ) : (
              <div className="flex gap-2">
                <input
                  type="text"
                  value={texts[w.vocab_item_id] ?? ""}
                  onChange={(e) => setTexts((t) => ({ ...t, [w.vocab_item_id]: e.target.value }))}
                  onKeyDown={(e) => e.key === "Enter" && !st?.sending && submit(w, e.currentTarget.value)}
                  placeholder="Scrivi una frase in tedesco..."
                  className="flex-1 rounded-[10px] border border-border bg-[#FBF8F2] px-3 py-2.5 text-sm"
                />
                <button
                  onClick={() => submit(w, texts[w.vocab_item_id])}
                  disabled={st?.sending}
                  className="rounded-[10px] bg-accent px-4 text-sm font-semibold text-surface disabled:opacity-40"
                >
                  →
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
