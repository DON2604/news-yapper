// Mirrors the FastAPI Pydantic contracts in backend/api/app/schemas.

export type Category =
  | "polity"
  | "economy"
  | "science"
  | "international"
  | "environment"
  | "awards"
  | "sports"
  | "other";

export type Exam = "SSC" | "UPSC" | "STATE_PSC" | "BANKING" | "RAILWAYS" | "GENERAL";

export interface SourceRef {
  id: string;
  name: string;
  url: string;
  published_at: string | null;
  tier: string;
  role: string;
  is_demo: boolean;
}

export interface NewsItem {
  event_id: string;
  slug: string;
  category: Category;
  date: string;
  status: string;
  ai_status: "ready" | "pending" | "in_review";
  headline: string;
  tldr: string;
  exam_tags: Exam[];
  relevance_score: number;
  importance_score: number | null;
  sensitive: boolean;
  is_demo: boolean;
  correction_status: string;
  source_count: number;
  primary_source: SourceRef | null;
  last_updated_at: string;
  saved: boolean;
}

export interface ArticleDetail extends NewsItem {
  neutral_summary: string | null;
  banglish_summary: string | null;
  why_matters: string | null;
  context: string | null;
  key_facts: { claim: string; source_item_ids: string[] }[];
  mnemonics: string[];
  uncertainties: string[];
  verification: {
    verified_at: string | null;
    method: string | null;
    ai_provider: string | null;
    ai_model: string | null;
    prompt_version: string | null;
  } | null;
  sources: SourceRef[];
  relevance_reasons: string[];
  correction_note: string | null;
  practice_question_count: number;
  snapshot_id: string | null;
}

export interface NewsPage {
  items: NewsItem[];
  next_cursor: string | null;
  total: number;
}

export interface ArchiveDay {
  date: string;
  story_count: number;
  ai_count: number;
}

export interface NewsArchive {
  dates: ArchiveDay[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  body: string;
  status: "ready" | "pending" | "failed";
  cached: boolean;
  created_at: string;
}

export interface ChatThread {
  available: boolean;
  serious: boolean;
  pending: boolean;
  messages: ChatMessage[];
}

export interface Edition {
  id: string | null;
  edition_date: string;
  timezone: string;
  title: string | null;
  is_demo: boolean;
  is_fallback: boolean;
  published_at: string | null;
  items: NewsItem[];
  generated_count: number;
  pending_count: number;
}

export interface QuizQuestion {
  id: string;
  prompt: string;
  options: string[];
  exam_topic: Category;
  kind: "current_affairs" | "static_gk";
  difficulty: "easy" | "medium" | "hard";
  is_demo: boolean;
  event_slug: string | null;
  reason: string | null;
}

export interface AnsweredState {
  question_id: string;
  selected_index: number;
  is_correct: boolean;
  correct_index: number;
  explanation: string;
  evidence_urls: string[];
}

export interface QuizSession {
  id: string;
  type: string;
  session_date: string;
  started_at: string;
  completed_at: string | null;
  score: number;
  question_count: number;
  xp_earned: number;
  questions: QuizQuestion[];
  answers: AnsweredState[];
}

export interface DailyQuiz {
  date: string;
  target_count: number;
  pool_size: number;
  current_affairs_available: number;
  static_gk_available: number;
  session: QuizSession | null;
}

export interface AnswerResult extends AnsweredState {
  already_answered: boolean;
  mistake: { id: string; status: string; error_count: number } | null;
  progress: { answered: number; total: number; score: number };
}

export interface TopicStat {
  topic: string;
  attempts: number;
  correct: number;
  accuracy: number;
}

export interface FinishResult {
  session: QuizSession;
  topic_breakdown: TopicStat[];
  weak_topics: string[];
  xp_earned: number;
}

export type NoteColor = "mango" | "lavender" | "mint" | "pink";

export interface Note {
  id: string;
  title: string;
  body: string;
  color: NoteColor;
  tags: string[];
  exam_topic: string | null;
  board_x: number;
  board_y: number;
  pinned: boolean;
  archived: boolean;
  revision_version: number;
  snapshot_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Snapshot {
  id: string;
  article_id: string | null;
  event_slug: string | null;
  category: Category | null;
  saved_title: string;
  saved_banglish_summary: string;
  saved_key_facts: { claim: string; source_url: string | null }[];
  source_url: string | null;
  source_name: string | null;
  source_published_at: string | null;
  verified: boolean;
  is_demo: boolean;
  saved_at: string;
  article_available: boolean;
  article_updated_since_save: boolean;
  created: boolean;
}

export interface Mistake {
  id: string;
  question_id: string;
  prompt: string;
  options: string[];
  incorrect_choice: number;
  correct_choice: number;
  explanation: string;
  evidence_urls: string[];
  topic: string;
  error_count: number;
  correct_review_count: number;
  status: "active" | "resolved";
  review_after: string | null;
  added_at: string;
  last_wrong_at: string;
  last_reviewed_at: string | null;
  resolved_at: string | null;
}

export interface Flashcard {
  id: string;
  front: string;
  back: string;
  exam_topic: string | null;
  source_ref: { refs?: string[]; items?: { ref: string; type: string; title: string; url: string | null; verified: boolean }[] };
  due_at: string;
  interval_days: number;
  ease_factor: number;
  repetitions: number;
  lapses: number;
  last_reviewed_at: string | null;
  crunch_output_id: string | null;
}

export interface CrunchBrief {
  id: string;
  title: string;
  engine: string;
  created_at: string;
  bullet_count: number;
  flashcard_count: number;
}

export interface RevisionDue {
  flashcards: Flashcard[];
  due_flashcards: number;
  total_flashcards: number;
  mistakes_due: Mistake[];
  active_mistakes: number;
  upcoming: { date: string; count: number }[];
  recaps: CrunchBrief[];
}

export interface CrunchSettings {
  length: "short" | "detailed";
  language: "banglish" | "english";
  exam: Exam;
  flashcards: number;
  include_traps: boolean;
}

export interface CrunchJob {
  id: string;
  status: "queued" | "running" | "deferred" | "completed" | "failed";
  engine: "ai" | "offline";
  status_message: string | null;
  output_id: string | null;
  requested_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_code: string | null;
  item_count: number;
  cached: boolean;
}

export interface CrunchDisclosure {
  ai_available: boolean;
  primary_provider: string | null;
  fallback_providers: string[];
  recipients_with_current_consent: string[];
  consent: string;
  private_fallback_allowed_by_server: boolean;
}

export interface CrunchPreview {
  items: { type: "note" | "snapshot" | "mistake"; id: string; title: string; chars: number; verified: boolean }[];
  total_chars: number;
  token_estimate: number;
  max_chars: number;
  max_items: number;
  within_budget: boolean;
  digest: string;
  engine_resolved: "ai" | "offline";
  existing_job: CrunchJob | null;
  disclosure: CrunchDisclosure;
  warnings: string[];
}

export interface CrunchBullet {
  text: string;
  source_refs: string[];
  verified?: boolean;
}

export interface CrunchOutput {
  id: string;
  title: string;
  concise_bullets: CrunchBullet[];
  topic_sections: { topic: string; bullets: CrunchBullet[] }[];
  mnemonics: string[];
  exam_traps: CrunchBullet[];
  source_refs: { ref: string; type: string; id: string; title: string; url: string | null; verified: boolean }[];
  warnings: string[];
  engine: string;
  model: string | null;
  prompt_version: string;
  created_at: string;
  flashcards: Flashcard[];
}

export interface Preferences {
  target_exam: Exam;
  target_exams: Exam[];
  region: string;
  topics: Category[];
  banglish_intensity: number;
  daily_minutes: number;
  timezone: string;
  daily_goal: number;
  tone_preference: "chill" | "balanced" | "serious";
  study_reminders: boolean;
  reminder_time: string | null;
  crunch_ai_consent: "none" | "primary_only" | "allow_fallback";
  leaderboard_opt_in: boolean;
  onboarded_at: string | null;
}

export interface Me {
  id: string;
  display_name: string;
  email: string | null;
  is_admin: boolean;
  created_at: string;
  preferences: Preferences;
  demo_mode: boolean;
  crunch_ai: CrunchDisclosure;
}

export interface Progress {
  xp_total: number;
  level: number;
  level_floor_xp: number;
  next_level_xp: number;
  streak_current: number;
  streak_best: number;
  studied_today: boolean;
  today_answered: number;
  daily_goal: number;
  accuracy_overall: number | null;
  accuracy_by_topic: TopicStat[];
  weak_topics: string[];
  due_flashcards: number;
  active_mistakes: number;
  resolved_mistakes: number;
  recent_missed: { mistake_id: string; prompt: string; topic: string; error_count: number; status: string; last_wrong_at: string }[];
  activity: { date: string; count: number }[];
  totals: Record<string, number>;
}
