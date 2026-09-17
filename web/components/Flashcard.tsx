"use client";

import { blankExample } from "@/lib/vocab";

/** Carta stile Anki: fronte italiano + esempio bucato, retro tedesco.
 * Usata sia dal ripasso (tab Vocabolario) sia dalla fase finale della lezione. */
export function Flashcard({
  de,
  it,
  example_de,
  flipped,
  onFlip,
}: {
  de: string;
  it: string;
  example_de: string;
  flipped: boolean;
  onFlip: () => void;
}) {
  return (
    <div className="mb-[18px] cursor-pointer [perspective:1200px]" onClick={onFlip}>
      <div
        className="relative min-h-[220px] [transform-style:preserve-3d] transition-transform duration-500"
        style={{ transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)" }}
      >
        <div className="absolute inset-0 flex flex-col items-center justify-center rounded-[18px] border border-border bg-card p-6 text-center [backface-visibility:hidden]">
          <div className="font-serif text-[26px] font-semibold text-secondary">{it}</div>
          {example_de && (
            <div className="mt-4 font-serif text-[15px] italic text-muted">„{blankExample(example_de, de)}"</div>
          )}
          <div className="mt-4 text-xs text-faint">Tocca per girare</div>
        </div>
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2.5 rounded-[18px] bg-primary p-6 text-center text-surface [backface-visibility:hidden] [transform:rotateY(180deg)]">
          <div className="font-serif text-[26px] font-semibold">{de}</div>
          {example_de && (
            <div className="font-serif text-[13px] italic text-[#C7BFAD]">„{example_de}"</div>
          )}
        </div>
      </div>
    </div>
  );
}
