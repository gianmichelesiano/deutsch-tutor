"use client";

import type { ReactNode } from "react";

export type Screen = "home" | "lesson" | "vocab" | "progress";

const NAV: { key: Screen; label: string; icon: ReactNode }[] = [
  {
    key: "home",
    label: "Home",
    icon: (
      <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 11l9-8 9 8" />
        <path d="M5 10v10h14V10" />
      </svg>
    ),
  },
  {
    key: "lesson",
    label: "Lezione",
    icon: (
      <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      </svg>
    ),
  },
  {
    key: "vocab",
    label: "Vocabolario",
    icon: (
      <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="8" y1="6" x2="21" y2="6" />
        <line x1="8" y1="12" x2="21" y2="12" />
        <line x1="8" y1="18" x2="21" y2="18" />
        <line x1="3" y1="6" x2="3.01" y2="6" />
        <line x1="3" y1="12" x2="3.01" y2="12" />
        <line x1="3" y1="18" x2="3.01" y2="18" />
      </svg>
    ),
  },
  {
    key: "progress",
    label: "Progresso",
    icon: (
      <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="18" y1="20" x2="18" y2="10" />
        <line x1="12" y1="20" x2="12" y2="4" />
        <line x1="6" y1="20" x2="6" y2="14" />
      </svg>
    ),
  },
];

export function Shell({
  screen,
  onNavigate,
  children,
}: {
  screen: Screen;
  onNavigate: (s: Screen) => void;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-page">
      <div className="mx-auto flex min-h-screen w-full max-w-[480px] flex-col bg-surface shadow-[0_0_40px_rgba(0,0,0,0.08)]">
        <div className="flex-1 overflow-y-auto px-5 py-6">{children}</div>
        <div className="sticky bottom-0 flex border-t border-border bg-[#FBF8F2] px-2 pb-[calc(10px+env(safe-area-inset-bottom))] pt-2.5">
          {NAV.map((item) => {
            const active = screen === item.key;
            const color = active ? "text-accent" : "text-faint";
            return (
              <button
                key={item.key}
                onClick={() => onNavigate(item.key)}
                className={`flex flex-1 flex-col items-center gap-1 py-1.5 ${color}`}
              >
                {item.icon}
                <span className="text-[10px] font-semibold">{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
