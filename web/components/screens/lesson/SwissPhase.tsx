"use client";

import type { LessonDetail } from "@/lib/api";

export function SwissPhase({ lesson }: { lesson: LessonDetail }) {
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
