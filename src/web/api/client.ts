export type HealthResponse = {
  status: string;
  version: string;
  database: { status: string; path: string };
  vector_store: { status: string; backend: string; path: string };
  paths: Record<string, string>;
};

export type ProviderInfo = {
  name: string;
  available: boolean;
  mode?: string;
  output_dir?: string;
  command_hint?: string;
  [key: string]: unknown;
};

export type Objective = {
  id: string;
  domain_id: string;
  number: string;
  title: string;
  topic_id: string | null;
  source_count: number;
  note_count: number;
  quiz_count: number;
  latest_quiz_score: number | null;
};

export type Domain = {
  id: string;
  number: number;
  name: string;
  weight_percent: number;
  summary: string | null;
  objectives: Objective[];
};

export type ObjectivesResponse = {
  domains: Domain[];
  metadata: Record<string, unknown>;
};

export type TopicSummary = {
  id: string;
  objective_id: string;
  title: string;
  status: string;
  objective_number: string;
  objective_title: string;
  domain_name: string;
  created_at: string;
  updated_at: string;
};

export type Note = {
  id: string;
  title: string;
  body: string;
  provider: string;
  model: string | null;
  vault_path: string | null;
  created_at: string;
  citations: NoteCitation[];
};

export type NoteCitation = {
  id: string;
  source_chunk_id: string;
  label: string | null;
  quote: string | null;
  page_start: number | null;
  page_end: number | null;
  section: string | null;
  source_title: string;
  source_path: string | null;
  source_url: string | null;
};

export type SourceRecord = {
  id: string;
  source_type: string;
  title: string;
  path: string | null;
  url: string | null;
  content_type: string;
  status: string;
  error: string | null;
  created_at: string;
};

export type QuizQuestion = {
  id: string;
  prompt: string;
  options: string[];
  correct_option: number;
  rationale: string;
  difficulty: string;
  concept: string | null;
};

export type ExerciseRecommendation = {
  id: string;
  title: string;
  body: string;
  reason: string | null;
  status: string;
};

export type FeedbackItem = {
  id: string;
  body: string;
  create_followup_job: number;
  followup_job_id: string | null;
  created_at: string;
};

export type InvestigationJob = {
  id: string;
  topic_id: string | null;
  status: string;
  query: string | null;
  logs: string[];
  gaps: string[];
  artifact_ids: string[];
  error: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type TopicResponse = {
  topic: TopicSummary;
  notes: Note[];
  sources: SourceRecord[];
  quiz_questions: QuizQuestion[];
  exercises: ExerciseRecommendation[];
  feedback: FeedbackItem[];
  latest_job: { id: string; status: string } | null;
};

export type RagResult = {
  chunk_id: string;
  source_id: string;
  source_title: string;
  text: string;
  score: number;
  page_start?: number | null;
  page_end?: number | null;
  section?: string | null;
  [key: string]: unknown;
};

export type RagQueryResponse = {
  query: string;
  results: RagResult[];
};

export type QuizAttemptResponse = {
  id: string;
  quiz_question_id: string;
  selected_option: number;
  is_correct: boolean;
  score: number;
  missed_concepts: string[];
  rationale: string;
  created_at: string;
};

export type SourceIngestResponse = {
  source_id: string;
  chunk_count: number;
  vector_count: number;
  deduplicated: boolean;
};

export type InvestigationStartResponse = {
  job_id: string;
  status: string;
};

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: BodyInit | Record<string, unknown> | null;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  let body = options.body;

  if (body && typeof body === "object" && !(body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(body);
  }

  const response = await fetch(path, {
    ...options,
    headers,
    body: body as BodyInit | null | undefined,
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {
      // Keep the HTTP status text when the backend did not return JSON.
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export const api = {
  health: () => request<HealthResponse>("/health"),
  importObjectives: () => request<Record<string, unknown>>("/admin/import-objectives", { method: "POST" }),
  objectives: () => request<ObjectivesResponse>("/api/objectives"),
  topic: (topicId: string) => request<TopicResponse>(`/api/topics/${encodeURIComponent(topicId)}`),
  ragQuery: (payload: { query: string; k?: number; objective_id?: string | null; topic_id?: string | null }) =>
    request<RagQueryResponse>("/api/rag/query", { method: "POST", body: payload }),
  ingestSource: (payload: { path: string; source_type?: string; objective_ids?: string[]; topic_ids?: string[] }) =>
    request<SourceIngestResponse>("/api/sources/ingest", { method: "POST", body: payload }),
  startInvestigation: (topicId: string, payload: { query?: string | null }) =>
    request<InvestigationStartResponse>(`/api/topics/${encodeURIComponent(topicId)}/investigations`, {
      method: "POST",
      body: payload,
    }),
  generateTopicNote: (topicId: string, payload: { query?: string | null }) =>
    request<InvestigationStartResponse>(`/api/topics/${encodeURIComponent(topicId)}/investigations`, {
      method: "POST",
      body: { ...payload, mode: "host_codex" },
    }),
  investigation: (jobId: string) =>
    request<InvestigationJob>(`/api/investigations/${encodeURIComponent(jobId)}`),
  quizAttempt: (payload: { quiz_question_id: string; selected_option: number }) =>
    request<QuizAttemptResponse>("/api/quiz-attempts", { method: "POST", body: payload }),
  feedback: (topicId: string, payload: { body: string; create_followup_job?: boolean }) =>
    request<Record<string, string | null>>(`/api/topics/${encodeURIComponent(topicId)}/feedback`, {
      method: "POST",
      body: payload,
    }),
  runSlice: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>("/api/slice/run", { method: "POST", body: payload }),
  codexProvider: () => request<ProviderInfo>("/api/provider/codex"),
};
