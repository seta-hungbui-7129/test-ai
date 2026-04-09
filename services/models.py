"""
Pydantic schemas for MCQ data structures.
"""

from pydantic import BaseModel, Field
from typing import List


class MCQ(BaseModel):
    question: str = Field(..., min_length=5)
    options: List[str] = Field(..., min_length=4, max_length=4)
    answer: str = Field(...)
    explanation: str = Field(..., min_length=10)

    def model_post_init(self, __context) -> None:
        if self.answer not in self.options:
            raise ValueError(
                f"Answer '{self.answer}' not found in options: {self.options}"
            )


class MCQList(BaseModel):
    questions: List[MCQ] = Field(..., min_length=5, max_length=5)