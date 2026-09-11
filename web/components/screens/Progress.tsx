"use client";

import { Card } from "@/components/ui";
import type { ProgressData } from "@/lib/api";

const STATE_META: Record<string, { color: string; label: string }> = {
  new: { color: "#C99A3E", label: "Nuovo" },
  seen: { color: "#7C9473", label: "Visto" },
  used: { color: "#5F8B7A", label: "Usato" },
  consolidated: { color: "#2A3324", label: "Consolidato" },
};

export function ProgressScreen({ data }: { data: ProgressData }) {
  const total = data.total_vocab || 1;
  const pct = (n: number) => Math.round((n / total) * 1000) / 10;
  return (
    <div>
      <div className="mb-4 font-serif text-2xl font-semibold">Progresso</div>

      <div className="mb-5 grid grid-cols-2 gap-2.5">
        {[
          { v: data.total_vocab, l: "parole totali" },
          { v: data.counts.consolidated, l: "consolidate" },
          { v: data.completed_lessons, l: "lezioni completate" },
          { v: data.streak, l: "serie attuale" },
        ].map((s) => (
          <Card key={s.l} className="p-3.5">
            <div className="font-serif text-[26px] font-bold">{s.v}</div>
            <div className="text-xs text-muted">{s.l}</div>
          </Card>
        ))}
      </div>

      <div className="mb-2.5 font-serif text-lg font-semibold">Parole per stato</div>
      <div className="mb-2.5 flex h-3.5 overflow-hidden rounded-lg">
        {(["new", "seen", "used", "consolidated"] as const).map((s) => (
          <div key={s} style={{ width: `${pct(data.counts[s])}%`, background: STATE_META[s].color }} />
        ))}
      </div>
      <div className="mb-6 flex flex-wrap gap-3 text-xs text-secondary">
        {(["new", "seen", "used", "consolidated"] as const).map((s) => (
          <div key={s}>
            <span className="mr-1.5 inline-block h-2 w-2 rounded-full" style={{ background: STATE_META[s].color }} />
            {STATE_META[s].label} ({data.counts[s]})
          </div>
        ))}
      </div>

      <div className="mb-2.5 font-serif text-lg font-semibold">Percorso · 12 settimane</div>
      <div className="flex flex-col gap-2">
        {data.path.map((sc) => (
          <div
            key={sc.week}
            className={`flex items-center gap-3 rounded-xl border border-border bg-card px-3 py-2.5 ${
              sc.current ? "" : sc.completed ? "" : "opacity-55"
            }`}
          >
            <div
              className={`flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                sc.current
                  ? "bg-accent text-surface"
                  : sc.completed
                    ? "bg-ink text-surface"
                    : "bg-border text-muted"
              }`}
            >
              {sc.week}
            </div>
            <div className="flex-1">
              <div className="text-sm font-semibold">{sc.title}</div>
              <div className="text-xs text-muted">{sc.subtitle}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
