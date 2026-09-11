"use client";

import { useState } from "react";
import type { LessonDetail } from "@/lib/api";

export function IntroPhase({ lesson }: { lesson: LessonDetail }) {
  const [expanded, setExpanded] = useState(!lesson.intro_collapsed);
  const intro = lesson.intro;

  if (!intro) {
    return (
      <div>
        <div className="font-serif text-xl font-semibold">Einstieg</div>
        <div className="mb-4 text-[13px] text-muted">La situazione</div>
        <div className="rounded-[14px] border border-dashed border-border p-4 text-sm text-muted">
          Nessuna introduzione per questo scenario. Premi Avanti per iniziare.
        </div>
      </div>
    );
  }

  if (!expanded) {
    return (
      <div>
        <div className="font-serif text-xl font-semibold">Einstieg</div>
        <div className="mb-4 text-[13px] text-muted">La situazione · già letta in una lezione precedente</div>
        <div className="rounded-[14px] border border-border bg-card p-3.5">
          {intro.situation.slice(0, 2).map((line, i) => (
            <div key={i} className="font-serif text-base">{line.de}</div>
          ))}
          <button
            onClick={() => setExpanded(true)}
            className="mt-3 rounded-btn border border-border px-4 py-2 text-sm font-semibold text-primary"
          >
            Rileggi
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="font-serif text-xl font-semibold">Einstieg</div>
      <div className="mb-4 text-[13px] text-muted">La situazione · leggi prima di iniziare</div>

      <div className="mb-3 rounded-[14px] border border-border bg-card p-3.5">
        {intro.situation.map((line, i) => (
          <div key={i} className={i > 0 ? "mt-2.5" : ""}>
            <div className="font-serif text-base leading-snug">{line.de}</div>
            <div className="text-[13px] text-muted">{line.it}</div>
          </div>
        ))}
      </div>

      <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Beispieldialog · esempio</div>
      <div className="mb-3 flex flex-col gap-2">
        {intro.dialog.map((turn, i) => {
          const mine = turn.speaker === "Ich";
          return (
            <div key={i} className={`max-w-[85%] ${mine ? "self-end" : "self-start"}`}>
              <div className={`text-[10px] ${mine ? "text-right" : ""} text-muted`}>{turn.speaker}</div>
              <div
                className={`rounded-[14px] px-3 py-2 text-sm ${
                  mine ? "rounded-tr-sm bg-accent text-surface" : "rounded-tl-sm border border-border bg-card"
                }`}
              >
                <div>{turn.de}</div>
                <div className={`mt-0.5 text-[12px] ${mine ? "text-surface/80" : "text-muted"}`}>{turn.it}</div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Da sapere</div>
      <ul className="rounded-[14px] border border-border bg-card p-3.5 pl-7 text-sm text-secondary">
        {intro.notes_it.map((note, i) => (
          <li key={i} className={`list-disc ${i > 0 ? "mt-1.5" : ""}`}>{note}</li>
        ))}
      </ul>
    </div>
  );
}
