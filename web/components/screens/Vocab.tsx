"use client";

import { useEffect, useState } from "react";
import { api, type ReviewQueueItem, type VocabDetail, type VocabItem } from "@/lib/api";
import { Badge, BottomSheet, ErrorBanner, LoadingDots } from "@/components/ui";

const FILTERS = [
  { key: "all", label: "Tutte" },
  { key: "new", label: "Nuovo" },
  { key: "seen", label: "Visto" },
  { key: "used", label: "Usato" },
  { key: "consolidated", label: "Consolidato" },
];

export function VocabScreen() {
  const [tab, setTab] = useState<"review" | "list">("review");
  return (
    <div>
      <div className="mb-3.5 font-serif text-2xl font-semibold">Vocabolario</div>
      <div className="mb-[18px] flex rounded-btn bg-vocab-new-bg p-1">
        {(
          [
            { key: "review", label: "Ripassa" },
            { key: "list", label: "Elenco" },
          ] as const
        ).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 rounded-[9px] py-2 text-[13px] font-semibold ${
              tab === t.key ? "bg-card text-primary" : "text-muted"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "review" ? <ReviewTab /> : <ListTab />}
    </div>
  );
}

function ReviewTab() {
  const [queue, setQueue] = useState<ReviewQueueItem[] | null>(null);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null);
    api
      .reviewQueue()
      .then(setQueue)
      .catch((e) => setError(String(e.message)));
  };
  useEffect(load, []);

  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (queue === null) return <LoadingDots />;

  if (queue.length === 0) {
    return (
      <div className="rounded-card border border-border bg-card px-5 py-[60px] text-center">
        <div className="mb-2 font-serif text-xl font-semibold">Ripasso completato</div>
        <div className="mb-4 text-[13px] text-muted">Hai rivisto tutte le parole di oggi.</div>
      </div>
    );
  }
  if (index >= queue.length) {
    return (
      <div className="rounded-card border border-border bg-card px-5 py-[60px] text-center">
        <div className="mb-2 font-serif text-xl font-semibold">Ripasso completato</div>
        <div className="mb-4 text-[13px] text-muted">Hai rivisto tutte le {queue.length} parole di oggi.</div>
      </div>
    );
  }

  const card = queue[index];
  const blankExample = card.example_de.replace(new RegExp(escapeRegex(card.de.replace(/^(der|die|das)\s+/, "")), "i"), "____");

  const answer = (result: "correct" | "wrong") => {
    api.review(card.id, result).catch(() => {});
    setFlipped(false);
    setIndex((i) => i + 1);
  };

  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs text-muted">
        <div>
          Carta {index + 1} di {queue.length}
        </div>
        <Badge state={card.state} />
      </div>
      <div className="mb-4 h-1.5 overflow-hidden rounded bg-vocab-new-bg">
        <div className="h-full rounded bg-accent" style={{ width: `${(index / queue.length) * 100}%` }} />
      </div>
      <div className="mb-[18px] cursor-pointer [perspective:1200px]" onClick={() => setFlipped((f) => !f)}>
        <div
          className="relative min-h-[220px] [transform-style:preserve-3d] transition-transform duration-500"
          style={{ transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)" }}
        >
          <div className="absolute inset-0 flex flex-col items-center justify-center rounded-[18px] border border-border bg-card p-6 text-center [backface-visibility:hidden]">
            <div className="font-serif text-[26px] font-semibold text-secondary">{card.it}</div>
            <div className="mt-4 font-serif text-[15px] italic text-muted">„{blankExample}"</div>
            <div className="mt-4 text-xs text-faint">Tocca per girare</div>
          </div>
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2.5 rounded-[18px] bg-primary p-6 text-center text-surface [backface-visibility:hidden] [transform:rotateY(180deg)]">
            <div className="font-serif text-[26px] font-semibold">{card.de}</div>
            <div className="font-serif text-[13px] italic text-[#C7BFAD]">„{card.example_de}"</div>
          </div>
        </div>
      </div>
      {flipped && (
        <div className="flex gap-2.5">
          <button onClick={() => answer("wrong")} className="flex-1 rounded-btn bg-src-error-bg py-3.5 text-sm font-semibold text-src-error">
            Non la so
          </button>
          <button onClick={() => answer("correct")} className="flex-1 rounded-btn bg-vocab-used-bg py-3.5 text-sm font-semibold text-vocab-used">
            La so
          </button>
        </div>
      )}
    </div>
  );
}

function escapeRegex(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function ListTab() {
  const [vocab, setVocab] = useState<VocabItem[] | null>(null);
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");
  const [detail, setDetail] = useState<VocabDetail | null>(null);

  useEffect(() => {
    api.vocab().then(setVocab).catch(() => setVocab([]));
  }, []);

  if (vocab === null) return <LoadingDots />;
  if (vocab.length === 0) {
    return (
      <div>
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Cerca una parola..."
          className="mb-3.5 w-full rounded-btn border border-border bg-card px-3.5 py-3 text-sm"
        />
        <div className="rounded-card border border-dashed border-border-strong bg-card px-7 py-[56px] text-center">
          <div className="mx-auto mb-4 flex h-[52px] w-[52px] items-center justify-center rounded-full bg-vocab-new-bg text-vocab-new">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
            </svg>
          </div>
          <div className="font-serif text-lg font-semibold">Nessuna parola ancora</div>
          <div className="mt-1.5 text-[13px] text-muted">
            Le parole delle tue lezioni appariranno qui. Completa la prima lezione per iniziare a costruire il tuo vocabolario.
          </div>
        </div>
      </div>
    );
  }
  const filtered = vocab.filter(
    (v) =>
      (filter === "all" || v.state === filter) &&
      (q === "" || (v.de + " " + v.it).toLowerCase().includes(q.toLowerCase())),
  );

  const openDetail = (id: number) => {
    api.vocabDetail(id).then(setDetail).catch(() => {});
  };

  return (
    <div>
      <input
        type="text"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Cerca una parola..."
        className="mb-3.5 w-full rounded-btn border border-border bg-card px-3.5 py-3 text-sm"
      />
      <div className="mb-4 flex gap-2 overflow-x-auto pb-1">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`whitespace-nowrap rounded-pill px-3.5 py-2 text-[13px] font-semibold ${
              filter === f.key ? "bg-ink text-surface" : "bg-card text-secondary"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>
      <div className="flex flex-col gap-2">
        {filtered.map((v) => (
          <button
            key={v.id}
            onClick={() => openDetail(v.id)}
            className="flex items-center justify-between rounded-[14px] border border-border bg-card px-3.5 py-3 text-left"
          >
            <div>
              <div className="font-serif text-[15px] font-semibold">{v.de}</div>
              <div className="text-xs text-muted">{v.it}</div>
            </div>
            <Badge state={v.state} />
          </button>
        ))}
      </div>

      <BottomSheet open={detail !== null} onClose={() => setDetail(null)} title={detail?.de ?? ""}>
        {detail && (
          <div>
            <div className="mb-3 font-serif text-[15px] text-muted">{detail.it}</div>
            <div className="mb-3 flex flex-wrap gap-2 text-[13px]">
              {detail.gender && (
                <span className="rounded-lg bg-vocab-new-bg px-2 py-1 text-vocab-new">genere: {detail.gender}</span>
              )}
              {detail.plural && (
                <span className="rounded-lg bg-vocab-new-bg px-2 py-1 text-vocab-new">plurale: {detail.plural}</span>
              )}
              {detail.separable && (
                <span className="rounded-lg bg-vocab-new-bg px-2 py-1 text-vocab-new">separabile</span>
              )}
            </div>
            {detail.example_de && (
              <div className="mb-3 text-[13px] italic text-secondary">„{detail.example_de}"</div>
            )}
            <div className="mb-2 text-xs text-muted">
              Prossimo ripasso: {detail.next_review_at ? new Date(detail.next_review_at).toLocaleDateString("it-CH") : "—"}
            </div>
            {detail.user_sentences.length > 0 && (
              <div>
                <div className="mb-1.5 text-sm font-semibold text-secondary">Le tue frasi</div>
                {detail.user_sentences.map((s, i) => (
                  <div key={i} className={`mb-1.5 rounded-lg px-2.5 py-1.5 text-[13px] ${s.is_correct ? "bg-vocab-used-bg" : "bg-src-error-bg"}`}>
                    „{s.sentence}"
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </BottomSheet>
    </div>
  );
}
