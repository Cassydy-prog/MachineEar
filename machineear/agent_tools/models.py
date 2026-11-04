"""Input/output contracts for the three S2 tools (Pydantic v2)."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class AnalyzeAudioInput(Contract):
    recording_id: str = Field(min_length=1, max_length=100, description='ID registered by the application, never a filesystem path')
    machine_type: Literal['fan', 'pump']
    machine_id: Literal['id_00', 'id_02', 'id_04', 'id_06']


class AudioWindow(Contract):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    score: float

    @model_validator(mode='after')
    def check_interval(self):
        if self.end_seconds <= self.start_seconds:
            raise ValueError('Window end must follow start')
        return self


class AnalyzeAudioOutput(Contract):
    recording_id: str
    machine_type: Literal['fan', 'pump']
    machine_id: Literal['id_00', 'id_02', 'id_04', 'id_06']
    model: Literal['logmel_knn5_mean']
    anomaly_score: float
    threshold: float
    is_anomaly: bool
    duration_seconds: float = Field(gt=0)
    n_windows: int = Field(ge=1)
    windows: list[AudioWindow]

    @model_validator(mode='after')
    def check_prediction(self):
        if len(self.windows) != self.n_windows:
            raise ValueError('Window count does not match results')
        if self.is_anomaly != (self.anomaly_score > self.threshold):
            raise ValueError('Anomaly flag disagrees with score and frozen threshold')
        return self


class SearchManualsInput(Contract):
    query: str = Field(min_length=1, max_length=1000)
    machine_type: Literal['fan', 'pump']
    language: Literal['en', 'fr', 'auto', 'all']
    top_k: int = Field(ge=1, le=5)

    @field_validator('query')
    @classmethod
    def nonblank_query(cls, value):
        if not value.strip():
            raise ValueError('Query cannot be blank')
        return value


class Passage(Contract):
    chunk_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source_document: str = Field(min_length=1)
    pdf_page_number: int = Field(ge=1)
    citation: str = Field(min_length=1)
    semantic_similarity: float = Field(ge=-1, le=1)
    citation_verified: Literal[True]


class SearchManualsOutput(Contract):
    status: Literal['passages_for_review', 'no_supported_passages']
    passages: list[Passage] = Field(max_length=5)

    @model_validator(mode='after')
    def check_results(self):
        if (self.status == 'passages_for_review') != bool(self.passages):
            raise ValueError('Retrieval status disagrees with passage count')
        keys = [(p.source_document, p.pdf_page_number) for p in self.passages]
        if len(set(keys)) != len(keys):
            raise ValueError('Duplicate physical pages')
        return self


class SaveReportRevisionInput(Contract):
    report_id: str = Field(min_length=1, max_length=100)
    reviewed_text: str = Field(min_length=1, max_length=50000)
    approval_id: str = Field(min_length=1, max_length=100,
                             description='Single-use approval issued by trusted human-review code')


    @field_validator('reviewed_text')
    @classmethod
    def nonblank_report(cls, value):
        if not value.strip():
            raise ValueError('Report cannot be blank')
        return value


class SaveReportRevisionOutput(Contract):
    report_id: str
    revision_id: str
    status: Literal['saved']
    reviewer: str = Field(min_length=1)
    saved_at: str
    approved: Literal[True]
