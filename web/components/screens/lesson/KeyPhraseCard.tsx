import type { KeyPhrase } from "@/lib/api";

export function KeyPhraseCard({ kp }: { kp: KeyPhrase }) {
  return (
    <div className="mb-2.5 rounded-[14px] border border-border bg-card p-3.5">
      <div className="flex justify-between">
        <div className="font-serif text-base font-semibold">{kp.de}</div>
        <div className="text-[13px] text-muted">{kp.it}</div>
      </div>
      <div className="mt-1.5 text-[13px] italic text-secondary">„{kp.example}"</div>
    </div>
  );
}
