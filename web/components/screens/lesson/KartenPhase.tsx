"use client";

import { useState } from "react";
import { api, type LessonDetail } from "@/lib/api";
import { Badge } from "@/components/ui";
import { Flashcard } from "@/components/Flashcard";

/** Ultima fase della lezione: flashcard delle parole dovute oggi (self-grading).
 * Il voto va a POST /vocab/{id}/review con source=flashcard: aggiorna intervallo
 * e lapse SRS ma non conta per la consolidazione (non è un uso in frase). */
export function KartenPhase({ lesson }: { lesson: LessonDetail }) {
  const queue = lesson.karten_words ?? [];
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);

  const header = (
    <>
      <div className="font-serif text-xl font-semibold">Karten</div>
      <div className="mb-4 text-[13px] text-muted">Carte di ripasso · questa lezione e parole dovute</div>
    </>
  );

  if (queue.length === 0) {
    return (
      <div>
        {header}
        <div className="rounded-card border border-border bg-card px-5 py-[40px] text-center">
          <div className="mb-2 font-serif text-lg font-semibold">Nessuna carta da ripassare</div>
          <div className="text-[13px] text-muted">Sei in pari con il ripasso: puoi chiudere la lezione.</div>
        </div>
      </div>
    );
  }

  if (index >= queue.length) {
    return (
      <div>
        {header}
        <div className="rounded-card border border-border bg-card px-5 py-[40px] text-center">
          <div className="mb-2 font-serif text-lg font-semibold">Ripasso completato</div>
          <div className="text-[13px] text-muted">Hai rivisto tutte le {queue.length} carte di oggi.</div>
        </div>
      </div>
    );
  }

  const card = queue[index];
  const answer = (result: "correct" | "wrong") => {
    // non blocca la UI: la carta successiva non dipende dalla risposta salvata
    api.review(card.id, result).catch(() => {});
    setFlipped(false);
    setIndex((i) => i + 1);
  };

  return (
    <div>
      {header}
      <div className="mb-2 flex items-center justify-between text-xs text-muted">
        <div>
          Carta {index + 1} di {queue.length}
        </div>
        <Badge state={card.state} />
      </div>
      <div className="mb-4 h-1.5 overflow-hidden rounded bg-vocab-new-bg">
        <div className="h-full rounded bg-accent" style={{ width: `${(index / queue.length) * 100}%` }} />
      </div>
      <Flashcard
        de={card.de}
        it={card.it}
        example_de={card.example_de}
        flipped={flipped}
        onFlip={() => setFlipped((f) => !f)}
      />
      {flipped && (
        <div className="flex gap-2.5">
          <button
            onClick={() => answer("wrong")}
            className="flex-1 rounded-btn bg-src-error-bg py-3.5 text-sm font-semibold text-src-error"
          >
            Non la so
          </button>
          <button
            onClick={() => answer("correct")}
            className="flex-1 rounded-btn bg-vocab-used-bg py-3.5 text-sm font-semibold text-vocab-used"
          >
            La so
          </button>
        </div>
      )}
    </div>
  );
}
