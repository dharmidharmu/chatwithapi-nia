from typing import Dict
from dataclasses import dataclass

@dataclass
class PromptValidationResult:
    """Custom object to store refined prompt, parameter adherence, and justifications."""
    title: str
    original_prompt: str
    refined_prompt: str
    pre_evaluation_result: Dict[str, str]
    post_evaluation_result: Dict[str, str]
    complexity_assessment: str = None
    refinement_reason: str = None