"use client";

import { useEffect, useState } from "react";
import { api, type LessonDetail, type TestWord } from "@/lib/api";
import { blankExample } from "@/lib/vocab";

interface TestState {
  sending: boolean;
  is_correct?: boolean;
  correct_de?: string;
}

export function TestPhase({ lesson, onAnswered }: { lesson: LessonDetail; onAnswered: (n: number) => void }) {
  const words = lesson.test_words ?? [];
  const [states, setStates] = useState<Record<number, TestState>>({});
  const [texts, setTexts] = useState<Record<number, string>>({});

  useEffect(() => {
    onAnswered(Object.values(states).filter((s) => s.is_correct !== undefined).length);
  }, [states, onAnswered]);

  const answered = Object.values(states).filter((s) => s.is_correct !== undefined).length;
  const correct = Object.values(states).filter((s) => s.is_correct === true).length;

  const submit = (w: TestWord, override?: string) => {
    const answer = (override ?? texts[w.vocab_item_id] ?? "").trim();
    if (!answer) return;
    setStates((s) => ({ ...s, [w.vocab_item_id]: { sending: true } }));
    api
      .testAnswer(lesson.id, w.vocab_item_id, answer)
      .then((res) =>
        setStates((s) => ({
          ...s,
          [w.vocab_item_id]: { sending: false, is_correct: res.is_correct, correct_de: res.correct_de },
        })),
      )
      .catch(() =>
        setStates((s) => ({ ...s, [w.vocab_item_id]: { sending: false, is_correct: false, correct_de: w.de } })),
      );
  };

  return (
    <div>
      <div className="font-serif text-xl font-semibold">Test</div>
      <div className="mb-1 text-[13px] text-muted">Completa la frase con la parola giusta</div>
      <div className="mb-4 text-[13px] font-semibold text-vocab-used">
        {correct} corrette · {answered - correct} errori · {answered}/{words.length}
      </div>
      {words.map((w) => {
        const st = states[w.vocab_item_id];
        const blanked = blankExample(w.example_de, w.de);
        return (
          <div key={w.vocab_item_id} className="mb-2.5 rounded-[14px] border border-border bg-card p-3.5">
            <div className="font-serif text-[16px] font-semibold leading-relaxed">„{blanked}"</div>
            {st?.is_correct !== undefined ? (
              <div
                className={`mt-2.5 rounded-lg px-2.5 py-1.5 text-[13px] ${
                  st.is_correct ? "bg-vocab-used-bg text-vocab-used" : "bg-src-error-bg text-src-error"
                }`}
              >
                {st.is_correct ? "Richtig!" : `No — la risposta era „${st.correct_de}"`}
              </div>
            ) : (
              <div className="mt-2.5 flex gap-2">
                <input
                  type="text"
                  value={texts[w.vocab_item_id] ?? ""}
                  onChange={(e) => setTexts((t) => ({ ...t, [w.vocab_item_id]: e.target.value }))}
                  onKeyDown={(e) => e.key === "Enter" && !st?.sending && submit(w, e.currentTarget.value)}
                  placeholder="Scrivi la parola..."
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
