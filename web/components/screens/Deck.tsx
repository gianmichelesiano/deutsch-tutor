"use client";

import { useEffect, useState } from "react";
import { api, type DeckCard, type DeckNext, type DeckSummary } from "@/lib/api";
import { ErrorBanner, LoadingDots } from "@/components/ui";

const RATINGS = [
  { rating: 1, label: "Ancora", cls: "bg-src-error-bg text-src-error" },
  { rating: 2, label: "Difficile", cls: "bg-vocab-new-bg text-vocab-new" },
  { rating: 3, label: "Bene", cls: "bg-vocab-used-bg text-vocab-used" },
  { rating: 4, label: "Facile", cls: "bg-vocab-consolidated-bg text-vocab-consolidated" },
];

export function DeckScreen() {
  const [data, setData] = useState<DeckNext | null>(null);
  const [flipped, setFlipped] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    api
      .deckNext()
      .then(setData)
      .catch((e) => setError(String(e.message)));
  };
  useEffect(load, []);

  const answer = (rating: number) => {
    if (!data?.card || busy) return;
    setBusy(true);
    api
      .deckAnswer(data.card.id, rating)
      .then((next) => {
        setFlipped(false);
        setData(next);
      })
      .catch((e) => setError(String(e.message)))
      .finally(() => setBusy(false));
  };

  // Tastiera: Spazio gira la carta, 1–4 rispondono (solo a carta girata)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!data?.card) return;
      if (e.code === "Space") {
        e.preventDefault();
        setFlipped(true);
      } else if (flipped && ["1", "2", "3", "4"].includes(e.key)) {
        answer(Number(e.key));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (data === null) return <LoadingDots />;

  return (
    <div>
      <div className="mb-3.5 flex items-baseline justify-between">
        <div className="font-serif text-2xl font-semibold">Mazzo</div>
        <div className="flex gap-3 text-sm font-semibold tabular-nums">
          <span className="text-vocab-new" title="Nuove">{data.counts.new}</span>
          <span className="text-src-error" title="In apprendimento">{data.counts.learning}</span>
          <span className="text-vocab-used" title="Da ripassare">{data.counts.review}</span>
        </div>
      </div>
      {data.card === null ? (
        <DoneForToday />
      ) : (
        <div>
          <FlipCard key={data.card.id} card={data.card} flipped={flipped} onFlip={() => setFlipped(true)} />
          {flipped ? (
            <div className="grid grid-cols-4 gap-2">
              {RATINGS.map((r, i) => (
                <button
                  key={r.rating}
                  onClick={() => answer(r.rating)}
                  disabled={busy}
                  className={`flex flex-col items-center gap-0.5 rounded-btn py-3 text-[13px] font-semibold disabled:opacity-60 ${r.cls}`}
                >
                  {r.label}
                  <span className="text-[11px] font-medium opacity-80">{data.previews[i]}</span>
                </button>
              ))}
            </div>
          ) : (
            <button
              onClick={() => setFlipped(true)}
              className="w-full rounded-btn bg-ink py-3.5 text-sm font-semibold text-surface"
            >
              Mostra risposta
            </button>
          )}
          <div className="mt-3 hidden text-center text-[11px] text-faint sm:block">
            Spazio: gira · 1–4: rispondi
          </div>
        </div>
      )}
    </div>
  );
}

function FlipCard({ card, flipped, onFlip }: { card: DeckCard; flipped: boolean; onFlip: () => void }) {
  const deIt = card.direction === "de_it";
  const front = deIt ? card.de : card.it;
  const back = deIt ? card.it : card.de;
  // la frase nella lingua del fronte per prima, poi la traduzione
  const [example, exampleTr] = deIt ? [card.example_de, card.example_it] : [card.example_it, card.example_de];

  return (
    <div className="mb-[18px] cursor-pointer [perspective:1200px]" onClick={onFlip}>
      <div
        className="grid [transform-style:preserve-3d] transition-transform duration-500"
        style={{ transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)" }}
      >
        <div className="flex min-h-[240px] flex-col items-center justify-center rounded-[18px] border border-border bg-card p-6 text-center [backface-visibility:hidden] [grid-area:1/1]">
          <div className="mb-3 text-[11px] font-semibold uppercase tracking-wide text-faint">
            {deIt ? "→ italiano" : "→ tedesco"}
          </div>
          <div className="font-serif text-[26px] font-semibold text-secondary">{front}</div>
          <div className="mt-4 text-xs text-faint">Tocca per girare</div>
        </div>
        <div className="flex min-h-[240px] flex-col items-center justify-center gap-2.5 rounded-[18px] bg-primary p-6 text-center text-surface [backface-visibility:hidden] [grid-area:1/1] [transform:rotateY(180deg)]">
          <div className="text-[13px] text-[#C7BFAD]">{front}</div>
          <div className="font-serif text-[26px] font-semibold">{back}</div>
          {example && <div className="font-serif text-[14px] italic text-[#C7BFAD]">„{example}"</div>}
          {exampleTr && <div className="text-[13px] text-[#C7BFAD]">{exampleTr}</div>}
          {card.theme && (
            <div className="mt-1 rounded-lg bg-surface/10 px-2 py-0.5 text-[11px] text-[#C7BFAD]">{card.theme}</div>
          )}
        </div>
      </div>
    </div>
  );
}

function DoneForToday() {
  const [s, setS] = useState<DeckSummary | null>(null);
  useEffect(() => {
    api.deckSummary().then(setS).catch(() => {});
  }, []);
  if (s === null) return <LoadingDots />;

  if (s.total_notes === 0) {
    return (
      <div className="rounded-card border border-dashed border-border-strong bg-card px-7 py-[56px] text-center">
        <div className="font-serif text-lg font-semibold">Mazzo vuoto</div>
        <div className="mt-1.5 text-[13px] text-muted">
          Importa la Wortliste (.apkg o .tsv) con <code>python -m app.deck_import</code>.
        </div>
      </div>
    );
  }

  const stats = [
    { label: "Carte riviste oggi", value: s.reviewed_today },
    { label: "Parole iniziate", value: `${s.notes_started} / ${s.total_notes}` },
    { label: "Carte in ripasso", value: s.cards.review },
    {
      label: "Prossimo ripasso",
      value: s.next_due
        ? new Date(s.next_due).toLocaleString("it-CH", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
        : "—",
    },
  ];
  return (
    <div className="rounded-card border border-border bg-card px-5 py-8 text-center">
      <div className="mb-1 font-serif text-xl font-semibold">Fatto per oggi</div>
      <div className="mb-5 text-[13px] text-muted">Torna domani: {s.new_per_day} carte nuove al giorno.</div>
      <div className="grid grid-cols-2 gap-2.5 text-left">
        {stats.map((st) => (
          <div key={st.label} className="rounded-[12px] bg-surface px-3 py-2.5">
            <div className="text-[11px] text-muted">{st.label}</div>
            <div className="font-serif text-lg font-semibold">{st.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
