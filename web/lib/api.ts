// Client API per il backend FastAPI (via rewrite /api → backend).

export type VocabState = "new" | "seen" | "used" | "consolidated";

export interface WarmupWord {
  vocab_item_id: number;
  de: string;
  it: string;
  is_new: boolean;
  state: VocabState;
}

export interface KeyPhrase {
  de: string;
  it: string;
  example: string;
}

export interface SwissVariant {
  standard: string;
  swiss: string;
  it: string;
}

export interface IntroLine {
  de: string;
  it: string;
}

export interface IntroTurn {
  speaker: string;
  de: string;
  it: string;
}

export interface LessonIntro {
  situation: IntroLine[];
  dialog: IntroTurn[];
  notes_it: string[];
}

export interface RoleplayMessage {
  role: "user" | "agent";
  content: string;
  requested_words?: { it: string; de: string }[];
}

export interface HarvestWord {
  de: string;
  it: string | null;
  source: "requested" | "error" | "agent_used";
  vocab_item_id: number | null;
}

export interface HarvestCorrection {
  sentence: string;
  corrected: string;
  rule_it: string;
}

export interface TestWord {
  vocab_item_id: number;
  de: string;
  it: string;
  example_de: string;
}

export interface LessonDetail {
  id: number;
  scenario_id: number;
  scenario_title_de: string;
  scenario_title_it: string;
  role_label: string | null;
  lesson_type: string;
  status: string;
  current_phase: "intro" | "warmup" | "prep" | "roleplay" | "harvest" | "swiss" | "karten" | "test" | null;
  key_phrases: KeyPhrase[];
  swiss_variants: SwissVariant[];
  intro: LessonIntro | null;
  intro_collapsed: boolean;
  warmup_words: WarmupWord[] | null;
  roleplay_messages: RoleplayMessage[];
  dialogue_closed: boolean;
  harvest_words: HarvestWord[] | null;
  harvest_corrections: HarvestCorrection[] | null;
  test_words: TestWord[] | null;
  karten_words: ReviewQueueItem[] | null;
}

export interface HomeData {
  user_name: string;
  resume_lesson_id: number | null;
  next_scenario: { id: number; title_de: string; title_it: string; role_label: string | null };
  lesson_type: string;
  due_today: number;
  due_words: string[];
  streak: number;
  current_week: number;
}

export interface PathScenario {
  week: number;
  id: number;
  title: string;
  subtitle: string;
  completed: boolean;
  current: boolean;
}

export interface ProgressData {
  total_vocab: number;
  counts: Record<VocabState, number>;
  completed_lessons: number;
  streak: number;
  current_scenario: { id: number; title_de: string; title_it: string; week_number: number } | null;
  path: PathScenario[];
}

export interface ReviewQueueItem {
  id: number;
  de: string;
  it: string;
  state: VocabState;
  gender: string | null;
  plural: string | null;
  separable: boolean;
  example_de: string;
}

export interface VocabItem extends ReviewQueueItem {
  next_review_at: string | null;
}

export interface VocabDetail {
  id: number;
  de: string;
  it: string;
  gender: string | null;
  plural: string | null;
  separable: boolean;
  example_de: string;
  state: VocabState;
  next_review_at: string | null;
  user_sentences: { sentence: string; is_correct: boolean; feedback: string }[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  home: () => request<HomeData>("/api/home"),
  progress: () => request<ProgressData>("/api/progress"),
  vocab: () => request<VocabItem[]>("/api/vocab"),
  vocabDetail: (id: number) => request<VocabDetail>(`/api/vocab/${id}`),
  reviewQueue: () => request<ReviewQueueItem[]>("/api/vocab/review-queue"),
  review: (id: number, result: "correct" | "wrong") =>
    request<{ id: number; state: string; next_review_at: string | null }>(`/api/vocab/${id}/review`, {
      method: "POST",
      body: JSON.stringify({ result }),
    }),
  currentLesson: () => request<{ lesson: LessonDetail | null }>("/api/lessons/current"),
  createLesson: (scenarioId?: number, replaceInProgress = false) =>
    request<LessonDetail>("/api/lessons", {
      method: "POST",
      body: JSON.stringify({
        ...(scenarioId ? { scenario_id: scenarioId } : {}),
        ...(replaceInProgress ? { replace_in_progress: true } : {}),
      }),
    }),
  getLesson: (id: number) => request<LessonDetail>(`/api/lessons/${id}`),
  advance: (id: number, skipSwiss = false) =>
    request<LessonDetail>(`/api/lessons/${id}/advance`, { method: "POST", body: JSON.stringify({ skip_swiss: skipSwiss }) }),
  warmupAnswer: (id: number, vocab_item_id: number, sentence: string) =>
    request<{ is_correct: boolean; feedback_it: string; error_type: string; corrected_sentence: string | null }>(
      `/api/lessons/${id}/warmup/answer`,
      { method: "POST", body: JSON.stringify({ vocab_item_id, sentence }) },
    ),
  roleplayMessage: (id: number, content: string) =>
    request<{ agent_text: string; dialogue_closed: boolean; requested_words: { it: string; de: string }[] }>(
      `/api/lessons/${id}/roleplay/message`,
      { method: "POST", body: JSON.stringify({ content }) },
    ),
  testAnswer: (id: number, vocab_item_id: number, answer: string) =>
    request<{ vocab_item_id: number; is_correct: boolean; correct_de: string; it: string }>(
      `/api/lessons/${id}/test/answer`,
      { method: "POST", body: JSON.stringify({ vocab_item_id, answer }) },
    ),
  harvestConfirm: (id: number, vocab_item_ids: number[]) =>
    request<{ confirmed: number }>(`/api/lessons/${id}/harvest/confirm`, {
      method: "POST",
      body: JSON.stringify({ vocab_item_ids }),
    }),
  abandon: (id: number) => request<{ status: string }>(`/api/lessons/${id}/abandon`, { method: "POST" }),
  back: (id: number) => request<LessonDetail>(`/api/lessons/${id}/back`, { method: "POST" }),
};

export const PHASES = ["intro", "warmup", "prep", "roleplay", "harvest", "swiss", "karten"] as const;
export const PHASE_LABELS: Record<string, string> = {
  intro: "Einstieg",
  warmup: "Aufwärmen",
  prep: "Vorbereitung",
  roleplay: "Rollenspiel",
  harvest: "Ernte",
  swiss: "Schweiz",
  karten: "Karten",
};

export const REVIEW_PHASES = ["warmup", "test", "harvest", "swiss", "karten"] as const;
export const REVIEW_PHASE_LABELS: Record<string, string> = {
  warmup: "Aufwärmen",
  test: "Test",
  harvest: "Ernte",
  swiss: "Schweiz",
  karten: "Karten",
};

export const LESSON_TYPE_LABELS: Record<string, string> = {
  base: "base",
  variant: "variante",
  incident: "imprevisto",
  review: "ripasso",
};
