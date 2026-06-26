import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const objectivesPayload = {
  domains: [
    {
      id: "domain-1",
      number: 1,
      name: "AI Agent Fundamentals",
      weight_percent: 10,
      summary: "Agent architecture and interaction patterns.",
      objectives: [
        {
          id: "objective-1.1",
          domain_id: "domain-1",
          number: "1.1",
          title: "Explain agent architecture",
          topic_id: "topic-1.1",
          source_count: 2,
          note_count: 1,
          quiz_count: 1,
          latest_quiz_score: null,
        },
      ],
    },
    {
      id: "domain-2",
      number: 2,
      name: "RAG Systems",
      weight_percent: 12,
      summary: null,
      objectives: [
        {
          id: "objective-2.1",
          domain_id: "domain-2",
          number: "2.1",
          title: "Describe vector retrieval",
          topic_id: "topic-2.1",
          source_count: 0,
          note_count: 0,
          quiz_count: 0,
          latest_quiz_score: null,
        },
      ],
    },
  ],
  metadata: { exam_weight_discrepancy_flag: true },
};

const topicPayload = {
  topic: {
    id: "topic-1.1",
    objective_id: "objective-1.1",
    title: "Agent architecture",
    status: "new",
    objective_number: "1.1",
    objective_title: "Explain agent architecture",
    domain_name: "AI Agent Fundamentals",
    created_at: "2026-01-01",
    updated_at: "2026-01-01",
  },
  notes: [
    {
      id: "note-1",
      title: "Control loop notes",
      body: "Agents combine planning, tools, memory, and feedback loops.",
      provider: "codex",
      model: "gpt-integrated",
      vault_path: "Agent architecture.md",
      created_at: "2026-01-01",
    },
  ],
  sources: [
    {
      id: "source-1",
      source_type: "local_file",
      title: "Study guide",
      path: "guide.md",
      url: null,
      content_type: "text/markdown",
      status: "ready",
      error: null,
      created_at: "2026-01-01",
    },
  ],
  quiz_questions: [
    {
      id: "quiz-1",
      prompt: "What does an agent loop coordinate?",
      options: ["Planning and tool use", "Only CSS", "Only storage", "Only routing"],
      correct_option: 0,
      rationale: "The loop coordinates planning, actions, and observations.",
      difficulty: "easy",
      concept: "Agent loops",
    },
  ],
  exercises: [
    {
      id: "exercise-1",
      title: "Trace a workflow",
      body: "Map an agent task from prompt to observation.",
      reason: "Practice architecture vocabulary.",
      status: "open",
    },
  ],
  feedback: [{ id: "feedback-1", body: "Clarify memory types.", create_followup_job: 0, followup_job_id: null, created_at: "2026-01-01" }],
  jobs: [{ id: "job-1", topic_id: "topic-1.1", status: "completed", query: "agent loops", logs: ["done"], gaps: [], artifact_ids: [], error: null, created_at: "2026-01-01", updated_at: "2026-01-01", started_at: null, completed_at: null }],
};

function json(data: unknown, init?: ResponseInit) {
  return Promise.resolve(new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" }, ...init }));
}

beforeEach(() => {
  globalThis.fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === "/health") return json({ status: "ok", version: "0.1.0", database: { status: "ok", path: "/data/app.db" }, vector_store: { status: "ok", backend: "sqlite", path: "/data/chroma" }, paths: {} });
    if (url === "/api/provider/codex") return json({ name: "codex", available: false, mode: "operator", output_dir: "/inbox/codex" });
    if (url === "/api/objectives") return json(objectivesPayload);
    if (url === "/api/topics/topic-1.1") return json(topicPayload);
    if (url === "/api/rag/query") {
      const body = JSON.parse(String(init?.body));
      return json({
        query: body.query,
        results: [
          { chunk_id: "chunk-1", source_id: "source-1", source_title: "Study guide", text: "RAG retrieves cited chunks before synthesis.", score: 0.91, section: "Retrieval", page_start: 3 },
        ],
      });
    }
    if (url === "/api/quiz-attempts") {
      return json({ id: "attempt-1", quiz_question_id: "quiz-1", selected_option: 0, is_correct: true, score: 1, missed_concepts: [], rationale: "The loop coordinates planning, actions, and observations.", created_at: "2026-01-01" });
    }
    return json({ detail: "Not found" }, { status: 404 });
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("NCP-AAI frontend", () => {
  it("renders grouped domains and objective counts", async () => {
    render(<App initialEntries={["/objectives"]} />);

    expect(await screen.findByText(/AI Agent Fundamentals/)).toBeInTheDocument();
    expect(screen.getByText(/RAG Systems/)).toBeInTheDocument();
    expect(screen.getByText("1 objectives · 10% weight")).toBeInTheDocument();
    expect(screen.getByText("2 sources")).toBeInTheDocument();
  });

  it("renders topic notes, sources, quiz, exercises, feedback, jobs, and empty states", async () => {
    render(<App initialEntries={["/topics/topic-1.1"]} />);

    expect(await screen.findByText("Control loop notes")).toBeInTheDocument();
    expect(screen.getByText("Study guide")).toBeInTheDocument();
    expect(screen.getByText("What does an agent loop coordinate?")).toBeInTheDocument();
    expect(screen.getByText("Trace a workflow")).toBeInTheDocument();
    expect(screen.getByText("Clarify memory types.")).toBeInTheDocument();
    expect(screen.getByText("agent loops")).toBeInTheDocument();
  });

  it("submits a RAG query and renders cited chunks", async () => {
    const user = userEvent.setup();
    render(<App initialEntries={["/chat"]} />);

    await user.type(await screen.findByLabelText("Question"), "How does RAG ground answers?");
    await user.click(screen.getByRole("button", { name: /query knowledge base/i }));

    expect(await screen.findByText("Study guide")).toBeInTheDocument();
    expect(screen.getByText("RAG retrieves cited chunks before synthesis.")).toBeInTheDocument();
    expect(screen.getByText("Retrieval · page 3")).toBeInTheDocument();
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/rag/query", expect.objectContaining({ method: "POST" }));
  });

  it("submits a quiz answer and renders correctness with rationale", async () => {
    const user = userEvent.setup();
    render(<App initialEntries={["/topics/topic-1.1"]} />);

    const quizPanel = await screen.findByText("What does an agent loop coordinate?");
    const panel = quizPanel.closest(".quiz-flow") as HTMLElement;
    await user.click(within(panel).getByLabelText("Planning and tool use"));
    await user.click(within(panel).getByRole("button", { name: /submit answer/i }));

    expect(await screen.findByText("Correct")).toBeInTheDocument();
    expect(screen.getByText("The loop coordinates planning, actions, and observations.")).toBeInTheDocument();
  });

  it("renders API errors with useful recovery states", async () => {
    vi.mocked(globalThis.fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/health" || url === "/api/provider/codex") return json({ status: "ok", version: "0.1.0", database: { status: "ok", path: "" }, vector_store: { status: "ok", backend: "sqlite", path: "" }, paths: {}, name: "codex", available: false });
      if (url === "/api/objectives") return json({ detail: "database unavailable" }, { status: 500 });
      return json({}, { status: 404 });
    });

    render(<App initialEntries={["/objectives"]} />);

    expect(await screen.findByRole("alert", {}, { timeout: 3_000 })).toHaveTextContent("database unavailable");
  });
});
