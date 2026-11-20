from typing import Annotated, Literal

from pydantic import BaseModel, Field

EntityType = Literal[
    "Person", "Case", "Crime", "Location", "Vehicle", "Organisation",
    "Evidence", "PoliceStation", "OffenceSection", "TimeWindow",
]

RELATIONSHIPS = {
    "ACCUSED_IN": ("Person", "Case"),
    "SUSPECT_IN": ("Person", "Case"),
    "VICTIM_IN": ("Person", "Case"),
    "WITNESS_IN": ("Person", "Case"),
    "ASSOCIATED_WITH": ("Person", "Case"),
    "CO_ACCUSED_WITH": ("Person", "Person"),
    "KNOWS": ("Person", "Person"),
    "RELATIVE_OF": ("Person", "Person"),
    "OWNS_VEHICLE": ("Person", "Vehicle"),
    "USED_VEHICLE": ("Person", "Vehicle"),
    "MEMBER_OF": ("Person", "Organisation"),
    "INVOLVES_CRIME": ("Case", "Crime"),
    "OCCURRED_AT": ("Crime", "Location"),
    "OCCURRED_AT_TIME": ("Crime", "TimeWindow"),
    "HAS_EVIDENCE": ("Case", "Evidence"),
    "REGISTERED_AT": ("Case", "PoliceStation"),
    "CHARGED_UNDER": ("Case", "OffenceSection"),
    "SPOTTED_AT": ("Vehicle", "Location"),
    "RELATED_TO_CASE": ("Case", "Case"),
}


class Citation(BaseModel):
    doc_id: str
    fir_number: str
    page_number: int = Field(ge=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    verbatim_quote: str = Field(min_length=1)


class Node(BaseModel):
    id: str
    type: EntityType
    name: str
    properties: dict[str, str | list[str]] = Field(default_factory=dict)
    sources: list[Citation] = Field(min_length=1)


class Edge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    citation: Citation
    confidence: float = Field(default=1, ge=0, le=1)


class Chunk(Citation):
    chunk_id: str
    text: str
    embedding: list[float] = Field(min_length=384, max_length=384)


class Document(BaseModel):
    doc_id: str
    fir_number: str
    file_name: str
    file_hash_sha256: str
    document_type: str
    police_station: str
    uploaded_at: str
    raw_text: str
    pages: list[list[str]]
    demo: bool = False


class Review(BaseModel):
    review_id: str
    entity_type: EntityType
    source_entity: Node
    target_entity: Node
    confidence_score: float = Field(ge=0, le=1)
    match_rationale: str
    status: Literal["PENDING", "APPROVED", "REJECTED"] = "PENDING"
    created_at: str


class Query(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[Annotated[str, Field(max_length=1000)]] = Field(default_factory=list, max_length=80)
    pending_question: str | None = Field(None, max_length=1000)
    selected_id: str | None = Field(None, max_length=96)
    previous_cases: list[Annotated[str, Field(max_length=100)]] = Field(default_factory=list, max_length=50)
    previous_person: str | None = Field(None, max_length=96)


class Decision(BaseModel):
    decision: Literal["approve", "reject"]
