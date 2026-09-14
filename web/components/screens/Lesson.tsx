"use client";

import { useEffect, useState } from "react";
import { api, type LessonDetail } from "@/lib/api";
import { BottomSheet, ErrorBanner, LoadingDots, PhaseIndicator } from "@/components/ui";
import { WarmupPhase } from "./lesson/WarmupPhase";
import { TestPhase } from "./lesson/TestPhase";
import { PrepPhase } from "./lesson/PrepPhase";
import { RoleplayPhase } from "./lesson/RoleplayPhase";
import { HarvestPhase } from "./lesson/HarvestPhase";
import { SwissPhase } from "./lesson/SwissPhase";
import { KeyPhraseCard } from "./lesson/KeyPhraseCard";
import { IntroPhase } from "./lesson/IntroPhase";

export function LessonScreen({
  onExit,
  startScenarioId,
  onConsumeStart,
}: {
  onExit: () => void;
  /** Scenario scelto dal Percorso (Progresso): se non c'è una lezione in corso,
   * la lezione parte lì invece che dal Planer. */
  startScenarioId?: number;
  /** Invocato appena lo scenario scelto è stato usato, per non riproporlo
   * a un successivo ingresso nella tab Lezione. */
  onConsumeStart?: () => void;
}) {
  const [lesson, setLesson] = useState<LessonDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmAbandon, setConfirmAbandon] = useState(false);
  const [warmupAnswered, setWarmupAnswered] = useState(0);
  const [testAnswered, setTestAnswered] = useState(0);
  const [showPhrases, setShowPhrases] = useState(false);

  const load = (id?: number, scenarioId?: number) => {
    setError(null);
    (id ? api.getLesson(id) : api.createLesson(scenarioId))
      .then(setLesson)
      .catch((e) => setError(String(e.message)));
  };
  useEffect(() => {
    onConsumeStart?.();
    api
      .currentLesson()
      .then((r) => (r.lesson ? load(r.lesson.id) : load(undefined, startScenarioId)))
      .catch(() => load(undefined, startScenarioId));
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

  const isFirstPhase = phase === "intro" || (isReview && phase === "warmup");
  const isLastPhase = phase === "swiss";

  return (
    <div>
      <div className="mb-3.5 flex items-center gap-2.5">
        {(phase === "intro" || phase === "warmup") && (
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

      {phase === "intro" && <IntroPhase lesson={lesson} />}
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
          {phase === "roleplay" || (phase === "warmup" && !isReview) ? (
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
        {lesson.key_phrases.map((kp, i) => <KeyPhraseCard key={i} kp={kp} />)}
      </BottomSheet>
    </div>
  );
}
