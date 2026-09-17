// Helper condivisi sulle carte vocabolo (flashcard e test).

export function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Esempio tedesco con la parola obiettivo sostituita da ____. */
export function blankExample(example: string, de: string): string {
  const lemma = de.replace(/^(der|die|das)\s+/i, "").trim();
  if (!lemma) return example;
  return example.replace(new RegExp(escapeRegex(lemma), "i"), "____");
}
