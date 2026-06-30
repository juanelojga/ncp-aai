import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const mermaidRenderMock = vi.hoisted(() => vi.fn());

vi.mock("mermaid", () => ({
  default: {
    initialize: vi.fn(),
    render: mermaidRenderMock,
  },
}));

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
      body: "## Agent loops\n\nAgents combine planning, tools, memory, and feedback loops.\n\n```mermaid\nmindmap\n  root((Agent architecture [chunk-root]))\n    Key concepts [chunk-key]\n      Capability clarity [chunk-capability]\n    Feedback loops [chunk-feedback]\n```\n\n- Keep state visible",
      provider: "codex",
      model: "gpt-integrated",
      vault_path: "Agent architecture.md",
      created_at: "2026-01-01",
      citations: [
        {
          id: "citation-1",
          source_chunk_id: "chunk-1",
          label: "Study guide excerpt",
          quote: "Agents combine planning, tools, memory, and feedback loops.",
          page_start: 3,
          page_end: 3,
          section: "Agent loops",
          source_title: "Study guide",
          source_path: "guide.md",
          source_url: null,
        },
      ],
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
  latest_job: null,
};

function json(data: unknown, init?: ResponseInit) {
  return Promise.resolve(new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" }, ...init }));
}

beforeEach(() => {
  mermaidRenderMock.mockResolvedValue({
    svg: '<svg role="img" aria-label="Rendered topic mind map"><text>Key concepts</text><text>Capability clarity</text></svg>',
  });
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
    if (url === "/api/topics/topic-1.1/investigations") {
      return json({ job_id: "job-host", status: "needs_review" });
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

  it("renders the latest topic note as the primary surface with the right rail", async () => {
    render(<App initialEntries={["/topics/topic-1.1"]} />);

    expect(await screen.findByText("Control loop notes")).toBeInTheDocument();
    expect(screen.getByText("Agent loops")).toBeInTheDocument();
    expect(screen.getByText("Keep state visible")).toBeInTheDocument();
    expect(screen.getByText("Study guide excerpt")).toBeInTheDocument();
    expect(screen.getByText("Study guide")).toBeInTheDocument();
    expect(screen.getByText("What does an agent loop coordinate?")).toBeInTheDocument();
    expect(screen.getByText("Trace a workflow")).toBeInTheDocument();
    expect(screen.getByText("Clarify memory types.")).toBeInTheDocument();
    expect(screen.queryByText("Job history")).not.toBeInTheDocument();
  });

  it("renders Mermaid topic mind maps with a readable outline and source disclosure", async () => {
    render(<App initialEntries={["/topics/topic-1.1"]} />);

    expect(await screen.findByLabelText("Mind map")).toBeInTheDocument();
    expect(await screen.findAllByText("Key concepts")).toHaveLength(2);
    expect(screen.getAllByText("Capability clarity")).toHaveLength(2);
    expect(screen.getByText("chunk-key")).toBeInTheDocument();
    expect(screen.getByText("chunk-capability")).toBeInTheDocument();

    const source = screen.getByText("Source").closest("details") as HTMLElement;
    expect(within(source).getByText(/root\(\(Agent architecture \[chunk-root\]\)/)).toBeInTheDocument();
    expect(mermaidRenderMock).toHaveBeenCalledWith(expect.any(String), expect.not.stringContaining("[chunk-key]"));
  });

  it("keeps the mind map outline available when Mermaid rendering fails", async () => {
    mermaidRenderMock.mockRejectedValueOnce(new Error("Renderer failed"));

    render(<App initialEntries={["/topics/topic-1.1"]} />);

    expect(await screen.findByText(/Visual renderer unavailable/)).toBeInTheDocument();
    expect(screen.getByText("Key concepts")).toBeInTheDocument();
    expect(screen.getByText("Capability clarity")).toBeInTheDocument();
    expect(screen.getByText("Outline fallback")).toBeInTheDocument();
  });

  it("starts note regeneration from the topic page and shows host bridge status", async () => {
    const user = userEvent.setup();
    render(<App initialEntries={["/topics/topic-1.1"]} />);

    await user.click(await screen.findByRole("button", { name: /regenerate note/i }));

    expect(await screen.findByText(/Host Codex bridge is waiting/)).toBeInTheDocument();
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/topics/topic-1.1/investigations",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ mode: "host_codex" }),
      }),
    );
  });

  it("shows the host bridge waiting notice on reload from a pending job", async () => {
    globalThis.fetch = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/objectives") return json(objectivesPayload);
      if (url === "/api/topics/topic-1.1") {
        return json({ ...topicPayload, latest_job: { id: "job-host", status: "needs_review" } });
      }
      if (url === "/health") return json({ status: "ok", version: "0.1.0", database: { status: "ok", path: "/data/app.db" }, vector_store: { status: "ok", backend: "sqlite", path: "/data/chroma" }, paths: {} });
      return json({ detail: "Not found" }, { status: 404 });
    });

    render(<App initialEntries={["/topics/topic-1.1"]} />);

    expect(await screen.findByText(/Host Codex bridge is waiting/)).toBeInTheDocument();
  });

  it("switches between note versions with the version selector", async () => {
    const twoNotePayload = {
      ...topicPayload,
      notes: [
        { ...topicPayload.notes[0], id: "note-2", title: "Latest revision", body: "## Latest\n\nNewest synthesis.", created_at: "2026-02-01", citations: [] },
        { ...topicPayload.notes[0], id: "note-1", title: "Control loop notes", body: "## Older\n\nFirst synthesis.", created_at: "2026-01-01", citations: [] },
      ],
    };
    globalThis.fetch = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/objectives") return json(objectivesPayload);
      if (url === "/api/topics/topic-1.1") return json(twoNotePayload);
      if (url === "/health") return json({ status: "ok", version: "0.1.0", database: { status: "ok", path: "/data/app.db" }, vector_store: { status: "ok", backend: "sqlite", path: "/data/chroma" }, paths: {} });
      return json({ detail: "Not found" }, { status: 404 });
    });

    const user = userEvent.setup();
    render(<App initialEntries={["/topics/topic-1.1"]} />);

    expect(await screen.findByText("Newest synthesis.")).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox"), "note-1");
    expect(await screen.findByText("First synthesis.")).toBeInTheDocument();
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
