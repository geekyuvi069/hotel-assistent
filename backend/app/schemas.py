from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def last_is_user(self):
        if self.messages[-1].role != "user":
            raise ValueError("last message must be from the user")
        return self


class AvailabilityRequest(BaseModel):
    check_in: date
    check_out: date
    adults: int = Field(ge=1, le=10)

    @model_validator(mode="after")
    def dates_ordered(self):
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        return self


class Room(BaseModel):
    id: str
    name: str
    capacity: int
    price_per_night: int
    total: int


class AvailabilityResult(BaseModel):
    check_in: date
    check_out: date
    adults: int
    nights: int
    rooms: list[Room]


class ChatResponse(BaseModel):
    reply: str
    type: Literal["answer", "fallback", "needs_availability_input", "availability"]
    availability: AvailabilityResult | None = None
    sources: list[str] = []
    degraded: bool = False  # true when the LLM was unavailable and the keyword fallback answered
    request_id: str
