"""Public request/response contracts for version-scoped RM actions."""

from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from app.pipeline.schemas import ContractModel, ReviewRecord


class ReviewActionRequest(ContractModel):
    client_id: Annotated[str, Field(pattern=r"^CL-\d{4}$")]
    action: Literal["Approve", "Edit", "Reject"]
    text: Annotated[str, Field(max_length=1200)] = ""
    section: str | None = None
    reason: str | None = None
    run_id: Annotated[str, Field(pattern=r"^[a-f0-9]{12}$")] = Field(...)
    brief_version: Annotated[int, Field(ge=1)] = Field(...)

    @model_validator(mode="after")
    def action_fields(self):
        if self.action == "Edit":
            if not self.section or not self.text.strip():
                raise ValueError("Edit requires section and text")
        elif self.section is not None or self.text:
            raise ValueError("Approve and Reject carry no section or replacement text")
        return self


class ReviewActionResponse(ContractModel):
    review: ReviewRecord
    brief_version: int
    verification_report: dict[str, Any]


class DemoUpdateRequest(ContractModel):
    action: Literal["apply", "reset"]
