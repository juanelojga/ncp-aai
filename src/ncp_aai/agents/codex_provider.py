from pydantic import BaseModel, Field, model_validator

from ncp_aai.agents.base import AgentCapability, AgentProvider, AgentProviderInfo


class ProviderMetadata(BaseModel):
    provider: str = "codex"
    model: str | None = None
    prompt_version: str | None = None
    run_id: str | None = None


class CitationInput(BaseModel):
    source_chunk_id: str
    label: str | None = None
    quote: str | None = None


class QuizItemInput(BaseModel):
    prompt: str
    options: list[str] = Field(min_length=4, max_length=4)
    correct_option: int = Field(ge=0, le=3)
    rationale: str
    difficulty: str = "medium"
    concept: str | None = None
    citations: list[CitationInput] = Field(min_length=1)


class CodexOutputInput(BaseModel):
    provider_metadata: ProviderMetadata = Field(default_factory=ProviderMetadata)
    objective_id: str | None = None
    topic_id: str | None = None
    title: str
    note_body: str
    citations: list[CitationInput] = Field(min_length=1)
    quiz_items: list[QuizItemInput] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_mapping(self) -> "CodexOutputInput":
        if not self.objective_id and not self.topic_id:
            msg = "Codex output must include objective_id or topic_id"
            raise ValueError(msg)
        return self


class CodexOperatorProvider(AgentProvider):
    def info(self) -> AgentProviderInfo:
        return AgentProviderInfo(
            name="codex",
            mode="operator-driven-output-ingestion",
            model_identifier="codex-integrated-gpt",
            capabilities=[
                AgentCapability.OPERATOR_OUTPUT_INGESTION,
                AgentCapability.STRUCTURED_NOTES,
                AgentCapability.STRUCTURED_QUIZZES,
            ],
            tool_access_policy=(
                "The backend never invokes Codex headlessly. The operator runs Codex and submits "
                "structured output for validation and persistence."
            ),
        )
