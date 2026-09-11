"use client";

import type { ReactNode } from "react";
import { PHASES, PHASE_LABELS, REVIEW_PHASES, REVIEW_PHASE_LABELS } from "@/lib/api";

export const VOCAB_BADGE: Record<string, { bg: string; text: string; label: string }> = {
  new: { bg: "bg-vocab-new-bg", text: "text-vocab-new", label: "Nuovo" },
  seen: { bg: "bg-vocab-seen-bg", text: "text-vocab-seen", label: "Visto" },
  used: { bg: "bg-vocab-used-bg", text: "text-vocab-used", label: "Usato" },
  consolidated: { bg: "bg-vocab-consolidated-bg", text: "text-vocab-consolidated", label: "Consolidato" },
};

const SRC_TAG: Record<string, { bg: string; text: string; label: string }> = {
  requested: { bg: "bg-src-requested-bg", text: "text-src-requested", label: "Chiesta" },
  error: { bg: "bg-src-error-bg", text: "text-src-error", label: "Errore" },
  agent_used: { bg: "bg-src-agent-bg", text: "text-src-agent", label: "Usata dall'agente" },
  agent: { bg: "bg-src-agent-bg", text: "text-src-agent", label: "Usata dall'agente" },
};

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-card border border-border bg-card ${className}`}>{children}</div>;
}

export function Badge({ state }: { state: string }) {
  const b = VOCAB_BADGE[state] ?? VOCAB_BADGE.new;
  return (
    <span className={`rounded-lg px-2 py-0.5 text-[11px] font-semibold ${b.bg} ${b.text}`}>{b.label}</span>
  );
}

export function SourceTag({ source }: { source: string }) {
  const t = SRC_TAG[source] ?? SRC_TAG.requested;
  return (
    <span className={`whitespace-nowrap rounded-lg px-2 py-0.5 text-[11px] font-semibold ${t.bg} ${t.text}`}>
      {t.label}
    </span>
  );
}

export function Pill({ children }: { children: ReactNode }) {
  return <div className="rounded-[10px] bg-ink/10 px-2.5 py-1.5 text-xs font-medium">{children}</div>;
}

export function PrimaryButton({
  children,
  onClick,
  disabled = false,
  secondary = false,
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  secondary?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`rounded-btn px-3 py-3 text-sm font-semibold transition ${
        secondary
          ? "border border-border bg-card text-primary"
          : "bg-accent text-surface disabled:opacity-40"
      }`}
    >
      {children}
    </button>
  );
}

export function PhaseIndicator({ phase, lessonType = "base" }: { phase: string | null; lessonType?: string }) {
  const isReview = lessonType === "review";
  const phases: readonly string[] = isReview ? REVIEW_PHASES : PHASES;
  const labels: Record<string, string> = isReview ? REVIEW_PHASE_LABELS : PHASE_LABELS;
  const idx = phase ? phases.indexOf(phase) : -1;
  const dense = phases.length >= 6;
  return (
    <div className="flex gap-1.5">
      {phases.map((key, i) => {
        const barColor = i === idx ? "bg-accent" : i < idx ? "bg-ink" : "bg-border";
        const textColor = i === idx ? "text-primary" : "text-faint";
        const weight = i === idx ? "font-semibold" : "font-medium";
        return (
          <div key={key} className="min-w-0 flex-1">
            <div className={`h-1.5 rounded ${barColor}`} />
            <div className={`mt-1.5 truncate text-center ${dense ? "text-[9px]" : "text-[10px]"} ${textColor} ${weight}`}>
              {labels[key]}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function LoadingDots({ inline = false }: { inline?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1 ${inline ? "" : "py-2"}`}>
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted [animation-delay:0ms]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted [animation-delay:150ms]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted [animation-delay:300ms]" />
    </span>
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-card border border-src-error-bg bg-src-error-bg p-3 text-sm text-src-error">
      <div className="flex items-center justify-between gap-2">
        <span>{message}</span>
        {onRetry && (
          <button onClick={onRetry} className="shrink-0 rounded-lg bg-white px-2 py-1 text-xs font-semibold">
            Riprova
          </button>
        )}
      </div>
    </div>
  );
}

export function BottomSheet({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      <div className="absolute inset-0 bg-ink/40" onClick={onClose} />
      <div className="relative w-full max-w-[480px] rounded-t-[20px] bg-surface p-5 pb-[calc(24px+env(safe-area-inset-bottom))] shadow-2xl">
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-border-strong" />
        <div className="mb-3 flex items-center justify-between">
          <div className="font-serif text-lg font-semibold">{title}</div>
          <button onClick={onClose} className="rounded-full bg-vocab-new-bg p-1.5 text-muted">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="max-h-[60vh] overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}
