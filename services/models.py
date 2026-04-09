"""
Pydantic schemas for MCQ data structures.
Provides validation and type safety for AI-generated questions.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List


class MCQ(BaseModel):
    """Single Multiple Choice Question with validation."""

    question: str = Field(
        ...,
        min_length=5,
        description="The question text, clear and unambiguous.",
    )
    options: List[str] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Exactly 4 answer choices.",
    )
    answer: str = Field(
        ...,
        description="The correct answer — must exactly match one option.",
    )
    explanation: str = Field(
        ...,
        min_length=10,
        description="Brief explanation of why the answer is correct.",
    )

    @field_validator("answer")
    @classmethod
    def answer_must_match_option(cls, v: str, info) -> str:
        """Ensure the answer string exactly matches one of the options."""
        # Note: validation runs before all fields are set, so we defer to model_post_init
        return v

    def model_post_init(self, __context) -> None:
        """Post-initialization validation — checks answer exists in options."""
        if self.answer not in self.options:
            raise ValueError(
                f"Answer '{self.answer}' not found in options: {self.options}"
            )


class MCQList(BaseModel):
    """Wrapper for a list of MCQs returned from the API."""

    questions: List[MCQ] = Field(
        ...,
        min_length=5,
        max_length=5,
        description="Exactly 5 MCQs per generation.",
    )
