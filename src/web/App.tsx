import {
  Activity,
  BookOpen,
  Bot,
  CheckCircle2,
  Database,
  FileInput,
  GraduationCap,
  LayoutDashboard,
  MessageSquareText,
  Play,
  RefreshCw,
  Search,
  Settings,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { FormEvent, ReactNode, useMemo, useState } from "react";
import { NavLink, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { BrowserRouter, MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, Domain, Objective, QuizQuestion, RagResult, TopicResponse } from "./api/client";

const navItems = [
  { label: "Dashboard", path: "/", icon: LayoutDashboard },
  { label: "Objectives", path: "/objectives", icon: BookOpen },
  { label: "Study Chat", path: "/chat", icon: MessageSquareText },
  { label: "Investigations", path: "/investigations", icon: Bot },
  { label: "Sources", path: "/sources", icon: Database },
  { label: "Settings", path: "/settings", icon: Settings },
];

function createClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: 1,
      },
    },
  });
}

export function App({ initialEntries }: { initialEntries?: string[] }) {
  const [queryClient] = useState(() => createClient());
  const Router = initialEntries ? MemoryRouter : BrowserRouter;

  return (
    <QueryClientProvider client={queryClient}>
      <Router {...(initialEntries ? { initialEntries } : {})}>
        <AppShell />
      </Router>
    </QueryClientProvider>
  );
}

function AppShell() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const provider = useQuery({ queryKey: ["codex-provider"], queryFn: api.codexProvider });
  const objectives = useObjectives();
  const activeJobs = useMemo(() => countActiveJobs(objectives.data?.domains ?? []), [objectives.data]);

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brand">
          <GraduationCap aria-hidden="true" />
          <div>
            <strong>NCP-AAI</strong>
            <span>Study console</span>
          </div>
        </div>
        <nav className="nav-list">
          {navItems.map((item) => (
            <NavLink key={item.path} to={item.path} end={item.path === "/"}>
              <item.icon aria-hidden="true" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div>
            <p className="eyeline">Local study platform</p>
            <h1>Evidence-backed exam preparation</h1>
          </div>
          <div className="status-strip" aria-label="System status">
            <StatusPill label="Backend" value={health.data?.status ?? "checking"} state={health.data?.status === "ok" ? "ok" : health.isError ? "bad" : "pending"} />
            <StatusPill label="Provider" value={provider.data?.available ? "ready" : "operator"} state={provider.data?.available ? "ok" : "pending"} />
            <StatusPill label="Jobs" value={`${activeJobs} active`} state={activeJobs > 0 ? "pending" : "ok"} />
          </div>
        </header>

        <main className="content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/objectives" element={<Objectives />} />
            <Route path="/topics/:topicId" element={<TopicDetail />} />
            <Route path="/chat" element={<StudyChat />} />
            <Route path="/investigations" element={<Investigations />} />
            <Route path="/sources" element={<Sources />} />
            <Route path="/settings" element={<SettingsView />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function useObjectives() {
  return useQuery({ queryKey: ["objectives"], queryFn: api.objectives });
}

function StatusPill({ label, value, state }: { label: string; value: string; state: "ok" | "pending" | "bad" }) {
  return (
    <span className={`status-pill ${state}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </span>
  );
}

function Dashboard() {
  const objectives = useObjectives();
  const domains = objectives.data?.domains ?? [];
  const totals = summarizeDomains(domains);
  const weak = domains.flatMap((domain) => domain.objectives).filter((item) => item.note_count === 0 || item.quiz_count === 0).slice(0, 6);

  return (
    <Page title="Dashboard" intro="Track objective coverage, local corpus status, and where the next study pass should start.">
      <QueryState query={objectives} loadingLabel="Loading objective coverage">
        <div className="metric-grid">
          <Metric label="Domains" value={domains.length} detail="Imported from exam objectives" />
          <Metric label="Objectives" value={totals.objectives} detail={`${totals.weight}% declared exam weight`} />
          <Metric label="Sourced" value={totals.withSources} detail="Objectives with at least one source" />
          <Metric label="Quiz-ready" value={totals.withQuizzes} detail="Objectives with generated questions" />
        </div>

        <section className="panel">
          <SectionHeader title="Weak or empty areas" action={<NavLink to="/objectives" className="text-link">Open objectives</NavLink>} />
          {weak.length ? (
            <div className="table-list">
              {weak.map((objective) => (
                <ObjectiveRow key={objective.id} objective={objective} />
              ))}
            </div>
          ) : (
            <EmptyState icon={<CheckCircle2 />} title="Coverage looks complete" body="Every imported objective has source and quiz records. Continue with chat or topic review." />
          )}
        </section>

        <section className="panel">
          <SectionHeader title="Readiness" />
          <div className="notice">
            <ShieldAlert aria-hidden="true" />
            <p>Readiness scoring is provisional until more quiz attempts exist. The imported exam weights currently total 92%, so the dashboard reports coverage separately from readiness.</p>
          </div>
        </section>
      </QueryState>
    </Page>
  );
}

function Objectives() {
  const objectives = useObjectives();
  const importMutation = useMutation({
    mutationFn: api.importObjectives,
    onSuccess: () => objectives.refetch(),
  });

  return (
    <Page title="Objectives" intro="Browse the exam domains, objective coverage, generated notes, and quiz availability.">
      <div className="toolbar">
        <button className="button secondary" onClick={() => importMutation.mutate()} disabled={importMutation.isPending}>
          <RefreshCw aria-hidden="true" />
          {importMutation.isPending ? "Importing" : "Import objectives"}
        </button>
      </div>
      <QueryState query={objectives} loadingLabel="Loading objective tree">
        <div className="domain-stack">
          {objectives.data?.domains.map((domain) => (
            <section className="panel" key={domain.id}>
              <SectionHeader
                title={`${domain.number}. ${domain.name}`}
                meta={`${domain.objectives.length} objectives · ${domain.weight_percent}% weight`}
              />
              {domain.summary ? <p className="section-copy">{domain.summary}</p> : null}
              <div className="table-list">
                {domain.objectives.map((objective) => (
                  <ObjectiveRow key={objective.id} objective={objective} />
                ))}
              </div>
            </section>
          ))}
        </div>
      </QueryState>
    </Page>
  );
}

function ObjectiveRow({ objective }: { objective: Objective }) {
  const target = objective.topic_id ? `/topics/${objective.topic_id}` : "/objectives";
  return (
    <NavLink to={target} className="objective-row">
      <div>
        <strong>{objective.number}</strong>
        <span>{objective.title}</span>
      </div>
      <div className="row-stats" aria-label="Objective coverage">
        <Badge>{objective.source_count} sources</Badge>
        <Badge>{objective.note_count} notes</Badge>
        <Badge>{objective.quiz_count} quiz</Badge>
      </div>
    </NavLink>
  );
}

function TopicDetail() {
  const { topicId } = useParams();
  const topic = useQuery({
    queryKey: ["topic", topicId],
    queryFn: () => api.topic(topicId!),
    enabled: Boolean(topicId),
  });
  const queryClient = useQueryClient();
  const feedback = useMutation({
    mutationFn: (payload: { body: string; create_followup_job?: boolean }) => api.feedback(topicId!, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["topic", topicId] }),
  });

  return (
    <Page title={topic.data?.topic.title ?? "Topic detail"} intro={topic.data ? `${topic.data.topic.domain_name} · Objective ${topic.data.topic.objective_number}` : "Inspect topic material and study actions."}>
      <QueryState query={topic} loadingLabel="Loading topic detail">
        {topic.data ? <TopicBody topic={topic.data} onFeedback={(body) => feedback.mutate({ body, create_followup_job: true })} /> : null}
      </QueryState>
    </Page>
  );
}

function TopicBody({ topic, onFeedback }: { topic: TopicResponse; onFeedback: (body: string) => void }) {
  return (
    <div className="topic-grid">
      <section className="panel span-2">
        <SectionHeader title="Notes" meta={`${topic.notes.length} generated`} />
        {topic.notes.length ? topic.notes.map((note) => (
          <article className="stack-item" key={note.id}>
            <h3>{note.title}</h3>
            <p>{note.body}</p>
            <small>{note.provider}{note.model ? ` · ${note.model}` : ""}{note.vault_path ? ` · ${note.vault_path}` : ""}</small>
          </article>
        )) : <EmptyState icon={<BookOpen />} title="No notes yet" body="Run an investigation or ingest Codex output to generate grounded notes for this topic." />}
      </section>

      <section className="panel">
        <SectionHeader title="Quiz" meta={`${topic.quiz_questions.length} questions`} />
        {topic.quiz_questions.length ? <QuizFlow questions={topic.quiz_questions} /> : <EmptyState icon={<Sparkles />} title="No quiz questions" body="Quiz items appear after cited synthesis output is ingested." />}
      </section>

      <section className="panel">
        <SectionHeader title="Sources" meta={`${topic.sources.length} linked`} />
        {topic.sources.length ? topic.sources.map((source) => (
          <article className="stack-item compact" key={source.id}>
            <h3>{source.title}</h3>
            <p>{source.path ?? source.url ?? source.content_type}</p>
            <Badge>{source.status}</Badge>
          </article>
        )) : <EmptyState icon={<Database />} title="No linked sources" body="Ingest local source material from the inbox and attach it to this topic." />}
      </section>

      <section className="panel">
        <SectionHeader title="Exercises" meta={`${topic.exercises.length} open`} />
        {topic.exercises.length ? topic.exercises.map((exercise) => (
          <article className="stack-item compact" key={exercise.id}>
            <h3>{exercise.title}</h3>
            <p>{exercise.body}</p>
          </article>
        )) : <EmptyState icon={<Activity />} title="No exercises" body="Exercise recommendations will appear after synthesis identifies practice gaps." />}
      </section>

      <section className="panel">
        <SectionHeader title="Job history" meta={`${topic.jobs.length} jobs`} />
        {topic.jobs.length ? topic.jobs.map((job) => <JobItem key={job.id} job={job} />) : <EmptyState icon={<Bot />} title="No investigations" body="Start an investigation from the Investigations view to populate this history." />}
      </section>

      <section className="panel span-2">
        <SectionHeader title="Feedback" meta={`${topic.feedback.length} notes`} />
        <FeedbackForm onSubmit={onFeedback} />
        {topic.feedback.map((item) => (
          <article className="stack-item compact" key={item.id}>
            <p>{item.body}</p>
            <small>{item.followup_job_id ? `Follow-up job ${item.followup_job_id}` : "No follow-up job"}</small>
          </article>
        ))}
      </section>
    </div>
  );
}

function QuizFlow({ questions }: { questions: QuizQuestion[] }) {
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const question = questions[index];
  const attempt = useMutation({
    mutationFn: () => api.quizAttempt({ quiz_question_id: question.id, selected_option: selected ?? 0 }),
  });

  function next() {
    setSelected(null);
    attempt.reset();
    setIndex((current) => Math.min(current + 1, questions.length - 1));
  }

  return (
    <div className="quiz-flow">
      <p className="quiz-count">Question {index + 1} of {questions.length}</p>
      <h3>{question.prompt}</h3>
      <div className="option-list">
        {question.options.map((option, optionIndex) => (
          <label key={option} className="option">
            <input type="radio" name={question.id} checked={selected === optionIndex} onChange={() => setSelected(optionIndex)} />
            <span>{option}</span>
          </label>
        ))}
      </div>
      <div className="button-row">
        <button className="button primary" onClick={() => attempt.mutate()} disabled={selected === null || attempt.isPending}>
          <CheckCircle2 aria-hidden="true" />
          Submit answer
        </button>
        <button className="button secondary" onClick={next} disabled={index === questions.length - 1}>
          Next
        </button>
      </div>
      {attempt.data ? (
        <div className={`result ${attempt.data.is_correct ? "correct" : "incorrect"}`}>
          <strong>{attempt.data.is_correct ? "Correct" : "Review this concept"}</strong>
          <p>{attempt.data.rationale}</p>
        </div>
      ) : null}
      {attempt.isError ? <ErrorBox message={(attempt.error as Error).message} /> : null}
    </div>
  );
}

function StudyChat() {
  const [query, setQuery] = useState("");
  const [topicId, setTopicId] = useState("");
  const rag = useMutation({
    mutationFn: () => api.ragQuery({ query, k: 5, topic_id: topicId || null }),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (query.trim()) rag.mutate();
  }

  return (
    <Page title="Study Chat" intro="Ask retrieval-first questions and inspect the exact chunks used for grounding.">
      <section className="panel">
        <form className="chat-form" onSubmit={submit}>
          <label>
            Question
            <textarea value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ask about agent architecture, RAG, evaluation, or a specific objective..." />
          </label>
          <label>
            Topic ID filter
            <input value={topicId} onChange={(event) => setTopicId(event.target.value)} placeholder="Optional, e.g. topic-1.1" />
          </label>
          <button className="button primary" disabled={rag.isPending || !query.trim()}>
            <Search aria-hidden="true" />
            Query knowledge base
          </button>
        </form>
      </section>
      <section className="panel">
        <SectionHeader title="Retrieved chunks" meta={rag.data ? `${rag.data.results.length} results` : undefined} />
        {rag.isPending ? <Skeleton label="Searching local vector store" /> : null}
        {rag.isError ? <ErrorBox message={(rag.error as Error).message} /> : null}
        {rag.data?.results.length ? <RagResults results={rag.data.results} /> : null}
        {rag.data && rag.data.results.length === 0 ? <EmptyState icon={<Search />} title="No matching chunks" body="Try a broader query or ingest more source material before asking again." /> : null}
      </section>
    </Page>
  );
}

function RagResults({ results }: { results: RagResult[] }) {
  return (
    <div className="result-list">
      {results.map((result) => (
        <article className="rag-result" key={result.chunk_id}>
          <div className="result-meta">
            <strong>{result.source_title}</strong>
            <Badge>{formatScore(result.score)}</Badge>
          </div>
          <p>{result.text}</p>
          <small>{[result.section, pageLabel(result)].filter(Boolean).join(" · ") || result.chunk_id}</small>
        </article>
      ))}
    </div>
  );
}

function Investigations() {
  const objectives = useObjectives();
  const [topicId, setTopicId] = useState("");
  const [query, setQuery] = useState("");
  const [jobId, setJobId] = useState("");
  const start = useMutation({
    mutationFn: () => api.startInvestigation(topicId, { query: query || null }),
    onSuccess: (data) => setJobId(data.job_id),
  });
  const job = useQuery({
    queryKey: ["investigation", jobId],
    queryFn: () => api.investigation(jobId),
    enabled: Boolean(jobId),
  });

  const firstTopic = objectives.data?.domains.flatMap((domain) => domain.objectives).find((objective) => objective.topic_id)?.topic_id;

  return (
    <Page title="Investigations" intro="Start focused agent passes for one topic and inspect queued or completed job details.">
      <section className="panel">
        <form className="inline-form" onSubmit={(event) => { event.preventDefault(); start.mutate(); }}>
          <label>
            Topic ID
            <input value={topicId} onChange={(event) => setTopicId(event.target.value)} placeholder={firstTopic ?? "topic-1.1"} />
          </label>
          <label>
            Query
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Optional investigation focus" />
          </label>
          <button className="button primary" disabled={!topicId || start.isPending}>
            <Play aria-hidden="true" />
            Start job
          </button>
        </form>
        {start.isError ? <ErrorBox message={(start.error as Error).message} /> : null}
      </section>
      <section className="panel">
        <SectionHeader title="Job inspector" />
        <label className="field">
          Job ID
          <input value={jobId} onChange={(event) => setJobId(event.target.value)} placeholder="Paste a job id" />
        </label>
        {job.isLoading ? <Skeleton label="Loading investigation" /> : null}
        {job.isError ? <ErrorBox message={(job.error as Error).message} /> : null}
        {job.data ? <JobItem job={job.data} expanded /> : <EmptyState icon={<Bot />} title="No job selected" body="Start a job or paste an existing job id to inspect logs and gaps." />}
      </section>
    </Page>
  );
}

function Sources() {
  const [path, setPath] = useState("");
  const [objectiveId, setObjectiveId] = useState("");
  const [topicId, setTopicId] = useState("");
  const ingest = useMutation({
    mutationFn: () => api.ingestSource({
      path,
      source_type: "local_file",
      objective_ids: objectiveId ? [objectiveId] : [],
      topic_ids: topicId ? [topicId] : [],
    }),
  });

  return (
    <Page title="Sources" intro="Ingest files already placed in the backend inbox. Browser uploads are intentionally out of scope for this MVP.">
      <section className="panel">
        <form className="inline-form" onSubmit={(event) => { event.preventDefault(); ingest.mutate(); }}>
          <label>
            Inbox file path
            <input value={path} onChange={(event) => setPath(event.target.value)} placeholder="study-guide.md" />
          </label>
          <label>
            Objective ID
            <input value={objectiveId} onChange={(event) => setObjectiveId(event.target.value)} placeholder="objective-1.1" />
          </label>
          <label>
            Topic ID
            <input value={topicId} onChange={(event) => setTopicId(event.target.value)} placeholder="topic-1.1" />
          </label>
          <button className="button primary" disabled={!path || ingest.isPending}>
            <FileInput aria-hidden="true" />
            Ingest source
          </button>
        </form>
        {ingest.data ? (
          <div className="result correct">
            <strong>{ingest.data.deduplicated ? "Source already indexed" : "Source indexed"}</strong>
            <p>{ingest.data.chunk_count} chunks · {ingest.data.vector_count} vectors · {ingest.data.source_id}</p>
          </div>
        ) : null}
        {ingest.isError ? <ErrorBox message={(ingest.error as Error).message} /> : null}
      </section>
    </Page>
  );
}

function SettingsView() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const provider = useQuery({ queryKey: ["codex-provider"], queryFn: api.codexProvider });

  return (
    <Page title="Settings" intro="Inspect backend health, vector store configuration, persistence paths, and Codex provider mode.">
      <div className="settings-grid">
        <section className="panel">
          <SectionHeader title="Backend health" />
          <QueryState query={health} loadingLabel="Checking backend">
            {health.data ? <KeyValue data={{
              Status: health.data.status,
              Version: health.data.version,
              Database: health.data.database.path,
              "Vector store": `${health.data.vector_store.backend} · ${health.data.vector_store.path}`,
            }} /> : null}
          </QueryState>
        </section>
        <section className="panel">
          <SectionHeader title="Codex provider" />
          <QueryState query={provider} loadingLabel="Checking provider">
            {provider.data ? <KeyValue data={{
              Name: String(provider.data.name ?? "codex"),
              Available: provider.data.available ? "yes" : "operator required",
              Mode: String(provider.data.mode ?? "local"),
              "Output directory": String(provider.data.output_dir ?? "not configured"),
            }} /> : null}
          </QueryState>
        </section>
      </div>
    </Page>
  );
}

function FeedbackForm({ onSubmit }: { onSubmit: (body: string) => void }) {
  const [body, setBody] = useState("");
  return (
    <form className="feedback-form" onSubmit={(event) => { event.preventDefault(); if (body.trim()) { onSubmit(body); setBody(""); } }}>
      <label>
        Follow-up note
        <textarea value={body} onChange={(event) => setBody(event.target.value)} placeholder="Capture confusion, missing evidence, or a follow-up investigation prompt." />
      </label>
      <button className="button secondary" disabled={!body.trim()}>Add feedback</button>
    </form>
  );
}

function JobItem({ job, expanded = false }: { job: { id: string; status: string; query: string | null; logs: string[]; gaps: string[]; error: string | null }; expanded?: boolean }) {
  return (
    <article className="stack-item compact">
      <div className="result-meta">
        <h3>{job.query ?? job.id}</h3>
        <Badge>{job.status}</Badge>
      </div>
      {job.error ? <ErrorBox message={job.error} /> : null}
      {expanded || job.logs.length ? <p>{job.logs.slice(-1)[0] ?? "No logs recorded yet."}</p> : null}
      {expanded && job.gaps.length ? <small>Gaps: {job.gaps.join(", ")}</small> : null}
    </article>
  );
}

function Page({ title, intro, children }: { title: string; intro: string; children: ReactNode }) {
  return (
    <div className="page">
      <div className="page-heading">
        <h2>{title}</h2>
        <p>{intro}</p>
      </div>
      {children}
    </div>
  );
}

function QueryState<T>({ query, loadingLabel, children }: { query: { isLoading: boolean; isError: boolean; error: unknown }; loadingLabel: string; children: ReactNode }) {
  if (query.isLoading) return <Skeleton label={loadingLabel} />;
  if (query.isError) return <ErrorBox message={(query.error as Error).message} />;
  return <>{children}</>;
}

function SectionHeader({ title, meta, action }: { title: string; meta?: string; action?: ReactNode }) {
  return (
    <div className="section-header">
      <div>
        <h2>{title}</h2>
        {meta ? <span>{meta}</span> : null}
      </div>
      {action}
    </div>
  );
}

function Metric({ label, value, detail }: { label: string; value: number | string; detail: string }) {
  return (
    <section className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <p>{detail}</p>
    </section>
  );
}

function Badge({ children }: { children: ReactNode }) {
  return <span className="badge">{children}</span>;
}

function EmptyState({ icon, title, body }: { icon: ReactNode; title: string; body: string }) {
  return (
    <div className="empty-state">
      {icon}
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
  );
}

function Skeleton({ label }: { label: string }) {
  return (
    <div className="skeleton" role="status" aria-label={label}>
      <span />
      <span />
      <span />
    </div>
  );
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div className="error-box" role="alert">
      <ShieldAlert aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}

function KeyValue({ data }: { data: Record<string, string> }) {
  return (
    <dl className="key-value">
      {Object.entries(data).map(([key, value]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function summarizeDomains(domains: Domain[]) {
  const objectives = domains.flatMap((domain) => domain.objectives);
  return {
    objectives: objectives.length,
    weight: domains.reduce((sum, domain) => sum + domain.weight_percent, 0),
    withSources: objectives.filter((objective) => objective.source_count > 0).length,
    withQuizzes: objectives.filter((objective) => objective.quiz_count > 0).length,
  };
}

function countActiveJobs(_domains: Domain[]) {
  return 0;
}

function formatScore(score: number) {
  if (score <= 1) return `${Math.round(score * 100)}% match`;
  return `${score.toFixed(2)} score`;
}

function pageLabel(result: RagResult) {
  if (result.page_start && result.page_end && result.page_start !== result.page_end) {
    return `pages ${result.page_start}-${result.page_end}`;
  }
  if (result.page_start) return `page ${result.page_start}`;
  return null;
}
