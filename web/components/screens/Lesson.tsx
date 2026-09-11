"use client";

import { useEffect, useRef, useState } from "react";
import { api, type LessonDetail, type TestWord, type WarmupWord } from "@/lib/api";
import { BottomSheet, ErrorBanner, LoadingDots, PhaseIndicator, SourceTag } from "@/components/ui";

interface WarmupState {
  sending: boolean;
  sentence?: string;
  is_correct?: boolean;
  feedback?: string;
  corrected_sentence?: string | null;
}

interface TestState {
  sending: boolean;
  is_correct?: boolean;
  correct_de?: string;
}

export function LessonScreen({ onExit }: { onExit: () => void }) {
  const [lesson, setLesson] = useState<LessonDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmAbandon, setConfirmAbandon] = useState(false);
  const [warmupAnswered, setWarmupAnswered] = useState(0);
  const [testAnswered, setTestAnswered] = useState(0);
  const [showPhrases, setShowPhrases] = useState(false);

  const load = (id?: number) => {
    setError(null);
    (id ? api.getLesson(id) : api.createLesson())
      .then(setLesson)
      .catch((e) => setError(String(e.message)));
  };
  useEffect(() => {
    api
      .currentLesson()
      .then((r) => (r.lesson ? load(r.lesson.id) : load()))
      .catch(() => load());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) return <div className="p-2"><ErrorBanner message={error} onRetry={() => load()} /></div>;
  if (lesson === null) return <LoadingDots />;

  const phase = lesson.current_phase;
  const isReview = lesson.lesson_type === "review";

  const advance = (skipSwiss = false) => {
    setBusy(true);
    api
      .advance(lesson.id, skipSwiss)
      .then(setLesson)
      .catch((e) => setError(String(e.message)))
      .finally(() => setBusy(false));
  };

  const goBack = () => {
    setBusy(true);
    api
      .back(lesson.id)
      .then(setLesson)
      .catch((e) => setError(String(e.message)))
      .finally(() => setBusy(false));
  };

  const abandon = () => {
    api.abandon(lesson.id).then(() => onExit()).catch(() => onExit());
  };

  const isFirstPhase = phase === "warmup";
  const isLastPhase = phase === "swiss";

  return (
    <div>
      <div className="mb-3.5 flex items-center gap-2.5">
        {phase === "warmup" && (
          <button onClick={() => setConfirmAbandon(true)} className="flex p-1.5">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>
        )}
        <div className="flex-1">
          <div className="font-serif text-lg font-semibold">{lesson.scenario_title_de}</div>
          <div className="text-xs text-muted">
            Lezione {lesson.lesson_type} · Scenario {lesson.scenario_id}
          </div>
        </div>
        {phase === "roleplay" && (
          <button
            onClick={() => setShowPhrases(true)}
            aria-label="Espressioni chiave"
            className="rounded-full border border-border bg-card p-2.5 text-secondary"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
            </svg>
          </button>
        )}
      </div>

      <div className="mb-[22px]">
        <PhaseIndicator phase={phase} lessonType={lesson.lesson_type} />
      </div>

      {phase === "warmup" && <WarmupPhase lesson={lesson} onAnswered={setWarmupAnswered} />}
      {phase === "test" && <TestPhase lesson={lesson} onAnswered={setTestAnswered} />}
      {phase === "prep" && <PrepPhase lesson={lesson} />}
      {phase === "roleplay" && <RoleplayPhase lesson={lesson} onUpdated={setLesson} />}
      {phase === "harvest" && <HarvestPhase lesson={lesson} onUpdated={setLesson} />}
      {phase === "swiss" && <SwissPhase lesson={lesson} />}

      {lesson.status === "completed" ? (
        <div className="mt-6 flex flex-col items-center gap-3">
          <div className="font-serif text-xl font-semibold">Lezione completata!</div>
          <button onClick={onExit} className="w-full rounded-btn bg-accent py-3 text-sm font-semibold text-surface">
            Torna alla Home
          </button>
        </div>
      ) : (
        <div className="mt-6 flex gap-2.5">
          {phase === "roleplay" ? (
            <button onClick={goBack} className="flex-1 rounded-btn border border-border bg-card py-3 text-sm font-semibold text-primary">
              Indietro
            </button>
          ) : (
            <div className="flex-1" />
          )}
          <button
            onClick={() => advance()}
            disabled={
              busy ||
              (phase === "warmup" && warmupAnswered < (lesson.warmup_words?.length ?? 0)) ||
              (phase === "test" && testAnswered < (lesson.test_words?.length ?? 0))
            }
            className="flex-[2] rounded-btn bg-accent py-3 text-sm font-semibold text-surface disabled:opacity-40"
          >
            {isLastPhase ? "Termina lezione" : "Avanti"}
          </button>
        </div>
      )}

      {confirmAbandon && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-6">
          <div className="w-full rounded-card bg-card p-5 text-center">
            <div className="mb-2 font-serif text-lg font-semibold">Abbandonare la lezione?</div>
            <div className="mb-4 text-sm text-muted">I progressi di questa lezione andranno persi.</div>
            <div className="flex gap-2.5">
              <button onClick={() => setConfirmAbandon(false)} className="flex-1 rounded-btn border border-border py-3 text-sm font-semibold">
                Annulla
              </button>
              <button onClick={abandon} className="flex-1 rounded-btn bg-src-error-bg py-3 text-sm font-semibold text-src-error">
                Abbandona
              </button>
            </div>
          </div>
        </div>
      )}

      <BottomSheet open={showPhrases} onClose={() => setShowPhrases(false)} title="Espressioni chiave">
        {lesson.key_phrases.map((kp, i) => (
          <div key={i} className="mb-2.5 rounded-[14px] border border-border bg-card p-3.5">
            <div className="flex justify-between">
              <div className="font-serif text-base font-semibold">{kp.de}</div>
              <div className="text-[13px] text-muted">{kp.it}</div>
            </div>
            <div className="mt-1.5 text-[13px] italic text-secondary">„{kp.example}"</div>
          </div>
        ))}
      </BottomSheet>
    </div>
  );
}

function WarmupPhase({ lesson, onAnswered }: { lesson: LessonDetail; onAnswered: (n: number) => void }) {
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

function TestPhase({ lesson, onAnswered }: { lesson: LessonDetail; onAnswered: (n: number) => void }) {
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

function PrepPhase({ lesson }: { lesson: LessonDetail }) {
  return (
    <div>
      <div className="font-serif text-xl font-semibold">Vorbereitung</div>
      <div className="mb-4 text-[13px] text-muted">Preparazione · le espressioni chiave dello scenario</div>
      {lesson.key_phrases.map((kp, i) => (
        <div key={i} className="mb-2.5 rounded-[14px] border border-border bg-card p-3.5">
          <div className="flex justify-between">
            <div className="font-serif text-base font-semibold">{kp.de}</div>
            <div className="text-[13px] text-muted">{kp.it}</div>
          </div>
          <div className="mt-1.5 text-[13px] italic text-secondary">„{kp.example}"</div>
        </div>
      ))}
    </div>
  );
}

function RoleplayPhase({ lesson, onUpdated }: { lesson: LessonDetail; onUpdated: (l: LessonDetail) => void }) {
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

function HarvestPhase({ lesson, onUpdated }: { lesson: LessonDetail; onUpdated: (l: LessonDetail) => void }) {
  const words = lesson.harvest_words ?? [];
  const [selected, setSelected] = useState<Set<number>>(
    () => new Set((lesson.harvest_words ?? []).map((w) => w.vocab_item_id).filter((x): x is number => x !== null)),
  );

  const toggle = (id: number) => {
    setSelected((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  };

  return (
    <div>
      <div className="font-serif text-xl font-semibold">Wortschatz-Ernte</div>
      <div className="mb-4 text-[13px] text-muted">Raccolta vocaboli · deseleziona quelle che già conosci</div>

      {(lesson.harvest_corrections ?? []).length > 0 && (
        <div className="mb-4">
          <div className="mb-2 text-sm font-semibold text-secondary">Correzioni</div>
          {lesson.harvest_corrections!.map((c, i) => (
            <div key={i} className="mb-2 rounded-[14px] border border-border bg-card p-3.5">
              <div className="text-[13px] text-secondary line-through decoration-src-error">{c.sentence}</div>
              <div className="text-[13px] font-semibold text-vocab-used">{c.corrected}</div>
              <div className="mt-0.5 text-xs text-muted">{c.rule_it}</div>
            </div>
          ))}
        </div>
      )}

      {words.map((w) => (
        <div
          key={w.vocab_item_id ?? w.de}
          onClick={() => w.vocab_item_id !== null && toggle(w.vocab_item_id)}
          className="mb-2 flex cursor-pointer items-center gap-3 rounded-[14px] border border-border bg-card px-3.5 py-3"
        >
          <div
            className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2 ${
              w.vocab_item_id !== null && selected.has(w.vocab_item_id) ? "border-ink bg-ink" : "border-border-strong bg-card"
            }`}
          >
            {w.vocab_item_id !== null && selected.has(w.vocab_item_id) && (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#F6F1E7" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 6L9 17l-5-5" />
              </svg>
            )}
          </div>
          <div className="flex-1">
            <span className="font-serif text-[15px] font-semibold">{w.de}</span>
            {w.it && <span className="text-[13px] text-muted"> — {w.it}</span>}
          </div>
          <SourceTag source={w.source} />
        </div>
      ))}

      <button
        onClick={() => {
          api.harvestConfirm(lesson.id, [...selected]).then(() => onUpdated({ ...lesson }));
        }}
        className="mt-1 w-full rounded-btn bg-accent py-3 text-sm font-semibold text-surface"
      >
        Conferma ({selected.size})
      </button>
    </div>
  );
}

function SwissPhase({ lesson }: { lesson: LessonDetail }) {
  return (
    <div>
      <div className="font-serif text-xl font-semibold">Schweizerdeutsch-Ecke</div>
      <div className="mb-4 text-[13px] text-muted">L'angolo svizzero tedesco</div>
      {lesson.swiss_variants.map((sv, i) => (
        <div key={i} className="mb-2.5 rounded-[14px] border border-border bg-card p-3.5">
          <div className="text-[13px] text-muted line-through">{sv.standard}</div>
          <div className="mt-1 font-serif text-[17px] font-semibold text-vocab-used">{sv.swiss}</div>
          <div className="mt-1 text-[13px] text-secondary">{sv.it}</div>
        </div>
      ))}
    </div>
  );
}

function escapeRegex(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function blankExample(example: string, de: string): string {
  const lemma = de.replace(/^(der|die|das)\s+/i, "").trim();
  return example.replace(new RegExp(escapeRegex(lemma), "i"), "____");
}
