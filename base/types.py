from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class Group(BaseModel):
    id: str | int
    name: str


class LessonType(str, Enum):
    practical = "practical"
    lecture = "lecture"
    laboratory = "laboratory"


class Lesson(BaseModel):
    name: str
    teacher: str
    type: LessonType
    location: str


class Schedule(BaseModel):
    name: str
    study_start_ts: int
    lesson_start_time: int
    lesson_length: int
    breaks: list[int]
    has_even_odd: bool
    weeks: dict[str, list[list[Lesson | None] | None]] | None = None  # If both odd and even exist
    week: list[list[Lesson | None] | None] = None  # If all weeks are the same
