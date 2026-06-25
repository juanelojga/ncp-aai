from enum import StrEnum

from pydantic import BaseModel, Field


class AgentCapability(StrEnum):
    OPERATOR_OUTPUT_INGESTION = "operator_output_ingestion"
    STRUCTURED_NOTES = "structured_notes"
    STRUCTURED_QUIZZES = "structured_quizzes"


class AgentProviderInfo(BaseModel):
    name: str
    mode: str
    model_identifier: str | None = None
    max_context: int | None = None
    capabilities: list[AgentCapability] = Field(default_factory=list)
    tool_access_policy: str = "operator-controlled"
    cost_metadata: dict[str, str | int | float | None] = Field(default_factory=dict)


class AgentRequest(BaseModel):
    topic_id: str | None = None
    objective_id: str | None = None
    query: str
    source_chunk_ids: list[str] = Field(default_factory=list)


class AgentResponse(BaseModel):
    provider: str
    model: str | None = None
    prompt_version: str | None = None
    output: dict


class AgentProvider:
    def info(self) -> AgentProviderInfo:
        raise NotImplementedError
