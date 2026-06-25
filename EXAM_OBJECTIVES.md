# NCP-AAI Exam Objectives Tracker

> Structured coverage tracker (source of truth for the readiness dashboard). Seeded from the official study guide.
> **Status: COMPLETE** — all 10 domains captured.
> ⚠️ Note: the official weights sum to **92%** (15+15+13+5+10+10+7+7+5+5) per the source document — flagged for verification.

## Weighted Domain Coverage

| # | Domain | Weight | Sub-objs | Note | ≥3 Quiz | Last |
|---|--------|:-----:|:--------:|:----:|:-------:|:----:|
| 1 | Agent Architecture and Design | 15% | 1.1–1.8 | ☐ | ☐ | — |
| 2 | Agent Development | 15% | 2.1–2.6 | ☐ | ☐ | — |
| 3 | Evaluation and Tuning | 13% | 3.1–3.5 | ☐ | ☐ | — |
| 4 | Deployment and Scaling | 5% | 4.1–4.5 | ☐ | ☐ | — |
| 5 | Cognition, Planning, and Memory | 10% | 5.1–5.5 | ☐ | ☐ | — |
| 6 | Knowledge Integration and Data Handling | 10% | 6.1–6.5 | ☐ | ☐ | — |
| 7 | NVIDIA Platform Implementation | 7% | 7.1–7.5 | ☐ | ☐ | — |
| 8 | Run, Monitor, and Maintain | 7% | 8.1–8.5 | ☐ | ☐ | — |
| 9 | Safety, Ethics, and Compliance | 5% | 9.1–9.5 | ☐ | ☐ | — |
| 10 | Human-AI Interaction and Oversight | 5% | 10.1–10.4 | ☐ | ☐ | — |

---

## Domain 1 — Agent Architecture and Design (15%)
Foundational structuring/design of agentic AI systems: how agents interact, reason, communicate.

| ID | Objective | Note | Quiz |
|----|-----------|:----:|:----:|
| 1.1 | Design user interfaces for intuitive human-agent interaction | ☐ | ☐ |
| 1.2 | Implement reasoning and action frameworks (e.g., ReAct) | ☐ | ☐ |
| 1.3 | Configure agent-to-agent communication protocols for collaboration | ☐ | ☐ |
| 1.4 | Manage short-term and long-term memory for context retention | ☐ | ☐ |
| 1.5 | Orchestrate multi-agent workflows and coordination | ☐ | ☐ |
| 1.6 | Apply logic trees, prompt chains, and stateful orchestration for multi-step reasoning | ☐ | ☐ |
| 1.7 | Integrate knowledge graphs to enable relational reasoning | ☐ | ☐ |
| 1.8 | Ensure adaptability and scalability of the agent's architecture | ☐ | ☐ |

- **Course:** Building Agentic AI Applications with LLMs
- **Seed readings:** Agentic AI in the Factory · Building Autonomous AI with NVIDIA Agentic NeMo · Three Building Blocks for … NVIDIA NIM Agent Blueprint · Agentic AI: Towards Autonomous AI Agents · Catch Me If You Can (Multi-Agent Fraud Detection) · What Are Multi-Agent Systems?

## Domain 2 — Agent Development (15%)
Practical building, integration, and enhancement of agents.

| ID | Objective | Note | Quiz |
|----|-----------|:----:|:----:|
| 2.1 | Engineer prompts and dynamic prompt chains for reliable performance | ☐ | ☐ |
| 2.2 | Integrate generative and multimodal models (text, vision, audio) | ☐ | ☐ |
| 2.3 | Build and connect custom tools, APIs, and functions for external system interaction | ☐ | ☐ |
| 2.4 | Implement error handling (retry logic, graceful failure recovery) | ☐ | ☐ |
| 2.5 | Develop dynamic conversation flows with real-time streaming and feedback | ☐ | ☐ |
| 2.6 | Evaluate and refine agent decision-making strategies | ☐ | ☐ |

- **Courses:** Building RAG Agents With LLMs · Building Agentic AI Applications with LLMs
- **Seed readings:** Optimization — NVIDIA Triton Inference Server · NVIDIA Agent Intelligence Toolkit Overview · Prompt Engineering & P-Tuning (NVIDIA Blog) · Multimodal AI RAG with LlamaIndex + NIM + Milvus · Transient Fault Handling / Circuit Breaker / Retry Pattern (Azure)

## Domain 3 — Evaluation and Tuning (13%)
Measuring, comparing, and optimizing agent performance.

| ID | Objective | Note | Quiz |
|----|-----------|:----:|:----:|
| 3.1 | Implement evaluation pipelines and task benchmarks to measure performance | ☐ | ☐ |
| 3.2 | Compare agent performance across tasks and datasets | ☐ | ☐ |
| 3.3 | Collect and integrate structured user feedback for iterative improvements | ☐ | ☐ |
| 3.4 | Tune model parameters (e.g., accuracy vs latency-efficiency trade-offs) | ☐ | ☐ |
| 3.5 | Analyze evaluation results to guide targeted optimization | ☐ | ☐ |

- **Courses:** Building Agentic AI Applications With LLMs · Evaluating RAG and Semantic Search Systems
- **Seed readings:** Powering the Next Generation of AI Agents · NVIDIA Agent Intelligence Toolkit (Overview/Tutorials/FAQ/API Server) · NVIDIA NeMo Agent Toolkit (GitHub) · Top 5 Agentic AI Challenges · AI Agents for Beginners — Production Patterns (Microsoft) · 5 Common Pitfalls in Agentic AI Adoption

## Domain 4 — Deployment and Scaling (5%)
Operationalizing and scaling agentic systems.

| ID | Objective | Note | Quiz |
|----|-----------|:----:|:----:|
| 4.1 | Deploy and orchestrate multi-agent systems at production scale | ☐ | ☐ |
| 4.2 | Apply MLOps practices for CI/CD workflows, monitoring, and governance | ☐ | ☐ |
| 4.3 | Profile performance and reliability under distributed system loads | ☐ | ☐ |
| 4.4 | Scale deployments using containerization (Docker, Kubernetes) with load balancing | ☐ | ☐ |
| 4.5 | Optimize deployment costs while ensuring high availability | ☐ | ☐ |

- **Courses:** Deploying RAG Pipelines for Production at Scale · Building Agentic AI Applications With LLMs · Building RAG Agents With LLMs
- **Seed readings:** Agentic AI in the Factory (Whitepaper) · NVIDIA TensorRT-LLM (GitHub) · DGX Cloud Benchmarking · Kubernetes Glossary (NVIDIA) · NVIDIA Nsight Systems · Kube Prometheus for GPU Telemetry · Scaling LLMs With Triton + TensorRT-LLM on Kubernetes · TensorRT-LLM Performance Analysis

## Domain 5 — Cognition, Planning, and Memory (10%)
Core cognitive processes: reasoning strategies, decision-making, memory management.

| ID | Objective | Note | Quiz |
|----|-----------|:----:|:----:|
| 5.1 | Implement memory mechanisms for short- and long-term context retention | ☐ | ☐ |
| 5.2 | Apply reasoning frameworks (chain-of-thought, task decomposition) | ☐ | ☐ |
| 5.3 | Engineer planning strategies for sequential and multi-step decision-making | ☐ | ☐ |
| 5.4 | Manage stateful orchestration to coordinate complex tasks and knowledge retention | ☐ | ☐ |
| 5.5 | Adapt reasoning strategies based on prior experiences and feedback | ☐ | ☐ |

- **Courses:** Building Agentic AI Applications With LLMs · Building RAG Agents with LLMs
- **Seed readings:** NVIDIA NeMo · LLMs Are In-Context Learners (arXiv:2310.10501) · NeMo RL Documentation · Jamba 1.5 Hybrid Architecture · Understanding the Planning of LLM Agents: A Survey · AI Agent Memory · MCP Agent Memory Types/Management/Implementation

## Domain 6 — Knowledge Integration and Data Handling (10%)
Integration of external knowledge and management of diverse data types.

| ID | Objective | Note | Quiz |
|----|-----------|:----:|:----:|
| 6.1 | Implement retrieval pipelines (RAG, embedded search, hybrid approaches) | ☐ | ☐ |
| 6.2 | Configure and optimize vector databases for fast retrieval | ☐ | ☐ |
| 6.3 | Build ETL pipelines to integrate enterprise/client data sources | ☐ | ☐ |
| 6.4 | Conduct data quality checks, augmentation, and preprocessing | ☐ | ☐ |
| 6.5 | Enable real-time access and reasoning over structured and unstructured knowledge | ☐ | ☐ |

- **Courses:** Building RAG Agents With LLMs · Adding New Knowledge to LLMs
- **Seed readings:** How to Make Your LLM More Accurate with RAG and Fine-Tuning (Towards Data Science)

## Domain 7 — NVIDIA Platform Implementation (7%)
Leveraging NVIDIA's AI hardware and software platforms.

| ID | Objective | Note | Quiz |
|----|-----------|:----:|:----:|
| 7.1 | Integrate NVIDIA NeMo Guardrails for compliance and safety enforcement | ☐ | ☐ |
| 7.2 | Deploy NVIDIA NIM microservices for high-performance inference | ☐ | ☐ |
| 7.3 | Optimize workflows with the NVIDIA NeMo Agent Toolkit | ☐ | ☐ |
| 7.4 | Leverage NVIDIA TensorRT-LLM and Triton Inference Server for latency reduction | ☐ | ☐ |
| 7.5 | Manage and optimize multimodal input pipelines on NVIDIA hardware | ☐ | ☐ |

- **Course:** Building RAG Agents With LLMs
- **Seed readings:** NeMo Guardrails (Developer + GitHub) · NeMo Framework Tuning/Best Practices · Triton (Optimization, Batchers, Backends) · TensorRT-LLM · NeMo Agent Toolkit · Agent Intelligence Toolkit · NVIDIA AIQ Toolkit · Deploy NIM Workloads · Llama Nemotron API · Llama-3.1-Nemotron-70B-Instruct deploy · AI Agents Blueprint · NeMo (GitHub)

## Domain 8 — Run, Monitor, and Maintain (7%)
Ongoing operation, monitoring, and maintenance post-deployment.

| ID | Objective | Note | Quiz |
|----|-----------|:----:|:----:|
| 8.1 | Define monitoring dashboards and reliability metrics | ☐ | ☐ |
| 8.2 | Track logs, errors, and anomalies for root cause diagnosis | ☐ | ☐ |
| 8.3 | Continuously benchmark deployed agents against prior versions | ☐ | ☐ |
| 8.4 | Implement automated tuning, retraining, and versioning in production | ☐ | ☐ |
| 8.5 | Ensure continuous uptime, transparency, and trust in live deployments | ☐ | ☐ |

- **Course:** Deploying RAG Pipelines in Production at Scale
- **Seed readings:** What Is AI Agent Evaluation? · Log, Trace, and Monitor · Time-Weighted Retriever · LangChain Tracing/Structured Outputs · LangSmith Model Evaluation · Monitoring ML Models in Production (data quality & integrity)

## Domain 9 — Safety, Ethics, and Compliance (5%)
Responsible operation, ethical standards, legal/regulatory compliance.

| ID | Objective | Note | Quiz |
|----|-----------|:----:|:----:|
| 9.1 | Design and enforce system security and audit trails | ☐ | ☐ |
| 9.2 | Integrate compliance guardrails (privacy, enterprise policy) | ☐ | ☐ |
| 9.3 | Mitigate bias and toxicity in outputs | ☐ | ☐ |
| 9.4 | Deploy layered safety frameworks (filters, escalation protocols) | ☐ | ☐ |
| 9.5 | Ensure compliance with licensing and regulatory standards | ☐ | ☐ |

- **Course:** Building RAG Agents with LLMs
- **Seed readings:** Safer LLM Apps with LangChain + NeMo Guardrails · NeMo Guardrails (GitHub) · AI/ML in Software as a Medical Device · EU AI Act proposal · Ethically Aligned Design (IEEE) · Securing GenAI Deployments with NIM + NeMo Guardrails · Metrics for Agentic AI · AI for Regulatory Compliance · Responsible AI Revisited

## Domain 10 — Human-AI Interaction and Oversight (5%)
Systems facilitating effective human oversight and interaction.

| ID | Objective | Note | Quiz |
|----|-----------|:----:|:----:|
| 10.1 | Build intuitive UIs with user-in-the-loop interaction | ☐ | ☐ |
| 10.2 | Design structured feedback loops that guide iterative agent improvements | ☐ | ☐ |
| 10.3 | Implement transparency mechanisms (explainable reasoning, decision traceability) | ☐ | ☐ |
| 10.4 | Enable human oversight and intervention for accountability and trust | ☐ | ☐ |

- **Course:** Building Agentic AI Applications with LLMs
- **Seed readings:** Agent Intelligence Toolkit · NVIDIA Data Flywheel Glossary · AI Agents With Human-in-the-Loop · Human-in-the-Loop AI (HolisticAI) · Human-in-the-Loop Agentic AI Systems (OneReach) · Aporia AI Guardrails · Chain-of-Thought (CoT) Prompting (Codecademy)

---

## NVIDIA platform artifacts (cross-domain study targets)
NeMo / Agentic NeMo / NeMo Agent Toolkit / NeMo Guardrails / NeMo RL · NIM (microservices + Agent Blueprints) · Triton Inference Server · TensorRT-LLM · Agent Intelligence Toolkit (AIQ Toolkit) · Data Flywheel · Nsight Systems · DGX Cloud · CUDA / GPU ops.

## Decisions
- **Exam date:** **November 4, 2026** (~4.5 months runway from Jun 15).
- **Model strategy:** synthesis runs through **Codex's integrated GPT models (GPT-XX)**. The
  operator drives Codex; the app ingests and validates its outputs. No separate cloud LLM keys
  (DeepSeek / GLM / MiniMax) or local Ollama models are configured for synthesis.
  - embeddings: `all-MiniLM-L6-v2` (local) — used by the app's RAG indexing, independent of Codex.
- **Web-search provider:** DuckDuckGo (free, no key) — resolved 2026-06-15.
