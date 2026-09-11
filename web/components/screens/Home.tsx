"use client";

import { PHASES, REVIEW_PHASES } from "@/lib/api";

import { Card } from "@/components/ui";
import type { HomeData } from "@/lib/api";

function todayIt(): string {
  return new Intl.DateTimeFormat("it-CH", { weekday: "long", day: "numeric", month: "long" }).format(new Date());
}

export function HomeScreen({
  data,
  onStart,
}: {
  data: HomeData;
  onStart: () => void;
}) {
  const typeLabel = data.lesson_type === "base" ? "base" : data.lesson_type;
  return (
    <div>
      <div className="mb-[22px] flex items-start justify-between">
        <div>
          <div className="text-[13px] tracking-wide text-muted capitalize">{todayIt()}</div>
          <div className="mt-0.5 font-serif text-[28px] font-semibold">Ciao, {data.user_name}</div>
        </div>
        <div className="whitespace-nowrap rounded-pill bg-ink px-3.5 py-2 text-[13px] font-semibold text-surface">
          Serie: {data.streak} lezioni
        </div>
      </div>

      <div className="relative overflow-hidden rounded-card bg-primary p-[22px] text-surface">
        <div className="text-[12px] uppercase tracking-[0.08em] text-[#C7BFAD]">
          Prossima lezione · Tipo {typeLabel}
        </div>
        <div className="mt-2 font-serif text-2xl font-semibold">{data.next_scenario.title_de}</div>
        <div className="mt-0.5 text-sm text-[#C7BFAD]">{data.next_scenario.title_it}</div>
        <div className="mt-4 flex gap-2">
          <div className="rounded-[10px] bg-surface/10 px-2.5 py-1.5 text-xs">30 minuti</div>
          <div className="rounded-[10px] bg-surface/10 px-2.5 py-1.5 text-xs">
            {(data.lesson_type === "review" ? REVIEW_PHASES : PHASES).length} fasi
          </div>
        </div>
        <button
          onClick={onStart}
          className="mt-[18px] w-full rounded-btn bg-accent py-3.5 text-[15px] font-semibold text-surface"
        >
          {data.resume_lesson_id ? "Riprendi la lezione" : "Inizia la lezione"}
        </button>
      </div>

      <div className="mt-[26px]">
        <div className="mb-2.5 font-serif text-lg font-semibold">Parole in scadenza oggi</div>
        {data.due_today === 0 ? (
          <Card className="flex items-center gap-4 p-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-vocab-new-bg text-vocab-new">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 6L9 17l-5-5" />
              </svg>
            </div>
            <div>
              <div className="text-[13px] font-semibold text-secondary">Nessuna parola in scadenza</div>
              <div className="text-xs text-muted">Hai ripassato tutto. Torna domani o inizia una lezione.</div>
            </div>
          </Card>
        ) : (
          <Card className="flex items-center justify-between p-4">
            <div>
              <div className="font-serif text-[30px] font-bold">{data.due_today}</div>
              <div className="text-[13px] text-muted">parole da ripassare</div>
            </div>
            <div className="flex max-w-[220px] flex-wrap justify-end gap-1.5">
              {data.due_words.map((w) => (
                <span key={w} className="rounded-lg bg-vocab-new-bg px-2 py-1 text-xs font-semibold text-vocab-new">
                  {w}
                </span>
              ))}
            </div>
          </Card>
        )}
      </div>

      <div className="mt-[26px]">
        <div className="mb-2.5 font-serif text-lg font-semibold">Il tuo percorso</div>
        <Card className="p-4">
          <div className="mb-2 flex justify-between text-[13px] text-secondary">
            <div>Settimana {data.current_week} di 12</div>
            <div>{data.next_scenario.title_de}</div>
          </div>
          <div className="h-2 overflow-hidden rounded-md bg-vocab-new-bg">
            <div
              className="h-full rounded-md bg-accent"
              style={{ width: `${Math.max(4, (data.current_week / 12) * 100)}%` }}
            />
          </div>
        </Card>
      </div>
    </div>
  );
}
