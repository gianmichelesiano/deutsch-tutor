"use client";

import type { LessonDetail } from "@/lib/api";
import { KeyPhraseCard } from "./KeyPhraseCard";

export function PrepPhase({ lesson }: { lesson: LessonDetail }) {
  return (
    <div>
      <div className="font-serif text-xl font-semibold">Vorbereitung</div>
      <div className="mb-4 text-[13px] text-muted">Preparazione · le espressioni chiave dello scenario</div>
      {lesson.key_phrases.map((kp, i) => <KeyPhraseCard key={i} kp={kp} />)}
    </div>
  );
}
