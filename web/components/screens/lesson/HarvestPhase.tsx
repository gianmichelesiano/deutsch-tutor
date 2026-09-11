"use client";

import { useState } from "react";
import { api, type LessonDetail } from "@/lib/api";
import { SourceTag } from "@/components/ui";

export function HarvestPhase({ lesson, onUpdated }: { lesson: LessonDetail; onUpdated: (l: LessonDetail) => void }) {
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
