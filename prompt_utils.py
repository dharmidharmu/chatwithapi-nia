import json
import logging
import re

from openai import AsyncAzureOpenAI
from PromptValidationResult import PromptValidationResult
from typing import Optional, Dict
from azure_openai_utils import (GPT_4o_ENDPOINT_URL, GPT_4o_API_KEY, GPT_4o_API_VERSION, GPT_4o_MODEL_NAME)

logger = logging.getLogger(__name__)

class PromptValidator:
    """Class to validate and refine prompts using an LLM for analysis."""
    
    # Define minimum and maximum parameters
    MINIMUM_PARAMETERS = [
        "task_definition",
        "output_format",
        "scope_and_constraints",
        "input_data",
        "clarity_check"
    ]

    MAXIMUM_PARAMETERS = [
        "example_inclusion",
        "edge_case_handling",
        "tone_and_persona",
        "ethical_guardrails",
        "performance_optimization",
        "testability",
        "domain_relevance"
    ]
    
    ALL_PARAMETERS = MINIMUM_PARAMETERS + MAXIMUM_PARAMETERS
    
    def __init__(self, llm_api=None):
        """Initialize with optional LLM API client (e.g., xAI API for Grok 3)."""
        self.llm_api = llm_api  # Placeholder for LLM API client
    
    async def call_llm(self, instruction: str, temperature: float = 0.3, top_p: float = 0.95) -> str:
        """
        Call the LLM API with enhanced prompt engineering capabilities.
        """
        
        # Default expert prompt engineer persona if no custom system prompt is provided
        prompt_refining_system_prompt = """You are an elite prompt engineering expert with extensive experience in analyzing, evaluating, and optimizing prompts.
            Your capabilities include:
            1. Rapid prompt dissection and structured analysis against established parameters
            2. Evidence-based evaluation with clear reasoning for each assessment
            3. Strategic prompt refinement that transforms weaknesses into strengths
            4. Comparative assessment of original vs. refined prompts with quantifiable improvements
            5. Pattern recognition across diverse prompt types and use cases

            Approach each prompt methodically:
            - Analyze without assumptions
            - Provide specific, actionable feedback with reasoning
            - Optimize for clarity, specificity, and effective constraint implementation
            - Ensure all output follows requested JSON schema precisely
            - Balance technical rigor with practical usability"""

        conversations = [
            {"role": "system", "content": prompt_refining_system_prompt},
            {"role": "user", "content": instruction}
        ]

        azure_openai_client = AsyncAzureOpenAI(
            azure_endpoint=GPT_4o_ENDPOINT_URL, 
            api_key=GPT_4o_API_KEY, 
            api_version=GPT_4o_API_VERSION)
        
        response = await azure_openai_client.chat.completions.create(
            model=GPT_4o_MODEL_NAME,
            messages=conversations,
            max_tokens=1200,  # Increased to accommodate justifications
            temperature=temperature,
            top_p=top_p,
        )
        
        model_response = response.choices[0].message.content
        return model_response

    def extract_json_from_response(self, response: str) -> str:
        """
        Extract valid JSON from a potentially noisy LLM response.
        Uses multiple strategies to find and validate JSON in the response.
        """
        if not response:
            return "{}"
            
        # Try to find JSON between triple backticks first (common format)
        json_match = re.search(r'```(?:json)?\s*({[\s\S]*?})\s*```', response)
        if json_match:
            potential_json = json_match.group(1)
            try:
                json.loads(potential_json)  # Validate it's proper JSON
                return potential_json
            except:
                pass  # If invalid, continue to other methods
                
        # Try to find the outermost JSON object with balanced braces
        stack = []
        start_index = None
        
        for i, char in enumerate(response):
            if char == '{':
                if not stack:  # First opening brace
                    start_index = i
                stack.append('{')
            elif char == '}':
                if stack and stack[-1] == '{':
                    stack.pop()
                    if not stack:  # We've found a complete JSON object
                        try:
                            json_candidate = response[start_index:i+1]
                            json.loads(json_candidate)  # Validate
                            return json_candidate
                        except:
                            pass  # If invalid, continue searching

        # If previous methods fail, try a more aggressive approach with regex
        try:
            # Look for any JSON-like structure with balanced braces
            json_pattern = r'{(?:[^{}]|(?R))*}'
            matches = re.findall(r'{.*}', response, re.DOTALL)
            
            # Try each match from longest to shortest
            for match in sorted(matches, key=len, reverse=True):
                try:
                    # Clean up common issues in LLM outputs
                    cleaned_json = self._clean_json_string(match)
                    json.loads(cleaned_json)
                    return cleaned_json
                except:
                    continue
        except:
            pass
            
        # Last resort: if JSON validation fails, return a minimal valid JSON
        logger.warning("Could not extract valid JSON from LLM response. Using fallback format.")
        return '{"error": "Could not parse valid JSON from response"}'
        
    def _clean_json_string(self, json_str):
        """Helper method to clean common JSON formatting issues in LLM outputs"""
        # Remove trailing commas before closing braces/brackets
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        # Fix missing quotes around keys
        json_str = re.sub(r'([{,])\s*([a-zA-Z0-9_]+)\s*:', r'\1"\2":', json_str)
        
        # Fix single quotes used instead of double quotes
        in_string = False
        result = []
        i = 0
        while i < len(json_str):
            if json_str[i] == '"':
                in_string = not in_string
            elif json_str[i] == "'" and not in_string:
                result.append('"')
                i += 1
                continue
            result.append(json_str[i])
            i += 1
        
        return ''.join(result)
    
    async def process_prompt_optimized(self, prompt: str, system_prompt: Optional[str] = None) -> PromptValidationResult:
        """
        Enhanced prompt processing that analyzes, evaluates with justification, refines, and re-evaluates prompts.
        
        Args:
            prompt: The user prompt to be evaluated and refined
            system_prompt: Optional system prompt that provides context or guidance
            
        Returns:
            PromptValidationResult object containing the refined prompt, parameter adherence, justifications,
            complexity assessment, and refinement reasoning
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        
        # Define parameter descriptions for clear analysis
        parameter_descriptions = {
            "task_definition": "Clearly defines the task or goal to be accomplished",
            "output_format": "Specifies the expected format and structure of the output",
            "scope_and_constraints": "Establishes clear boundaries and limitations for the task",
            "input_data": "Provides necessary context or data inputs needed for the task",
            "clarity_check": "Ensures instructions are unambiguous and easily understood",
            "example_inclusion": "Includes examples to demonstrate desired outputs or approaches",
            "edge_case_handling": "Addresses potential edge cases or unexpected scenarios",
            "tone_and_persona": "Specifies the desired communication style and personality",
            "ethical_guardrails": "Provides guidance to ensure ethical and responsible outputs",
            "performance_optimization": "Includes hints for efficiency or computational considerations",
            "testability": "Includes criteria for evaluating the success of the response",
            "domain_relevance": "Ensures contextual alignment with the domain or field of application"
        }

        evaluation_definitions = {
                "task_definition": {
                    "adherence": "true or false",
                    "justification": "detailed reasoning for the evaluation"
                },
                "output_format": {
                    "adherence": "true or false",
                    "justification": "detailed reasoning for the evaluation"
                },
                "scope_and_constraints": {
                    "adherence": "true or false", 
                    "justification": "detailed reasoning for the evaluation"
                },
                "input_data": {
                    "adherence": "true or false",
                    "justification": "detailed reasoning for the evaluation"
                },
                "clarity_check": {
                    "adherence": "true or false",
                    "justification": "detailed reasoning for the evaluation"
                },
                "example_inclusion": {
                    "adherence": "true or false",
                    "justification": "detailed reasoning for the evaluation"
                },
                "edge_case_handling": {
                    "adherence": "true or false",
                    "justification": "detailed reasoning for the evaluation"
                },
                "tone_and_persona": {
                    "adherence": "true or false",
                    "justification": "detailed reasoning for the evaluation"
                },
                "ethical_guardrails": {
                    "adherence": "true or false",
                    "justification": "detailed reasoning for the evaluation"
                },
                "performance_optimization": {
                    "adherence": "true or false",
                    "justification": "detailed reasoning for the evaluation"
                },
                "testability": {
                    "adherence": "true or false",
                    "justification": "detailed reasoning for the evaluation"
                },
                "domain_relevance": {
                    "adherence": "true or false",
                    "justification": "detailed reasoning for the evaluation"
                }
            }
        
        # Create the evaluation and refinement instruction
        refinement_instruction = f"""
        As an expert prompt engineer, analyze the following prompt and provide a detailed evaluation and refinement.
        
        # PART 1: ANALYSIS
        Analyze the prompt against these criteria:
        {json.dumps(parameter_descriptions, indent=2)}
        
        # PART 2: EVALUATION
        Evaluate the prompt against these parameters with detailed justification for each parameter.
        
        # PART 3: REFINEMENT
        Determine prompt complexity (simple or complex), whether it needs refinement, and if so, provide detailed recommendations.
        If the system prompt contains information that should be moved from the user prompt, make this transfer in your refinement.
        
        # PART 4: PROMPT ENGINEERING
        Create a refined version of the prompt that addresses all identified issues, optimizes parameter adherence, and maintains the original intent.
        If appropriate, move details from the user prompt to the system prompt based on best practices.
        
        # PART 5: COMPARATIVE EVALUATION
        Re-evaluate the refined prompt against the same parameters to demonstrate improvements.
        
        # INPUTS
        System prompt: {system_prompt or 'None'}
        User prompt: {prompt}
        Evaluation parameters: {evaluation_definitions}
        
        # OUTPUT FORMAT
        Return your analysis in this exact JSON format (do not include any explanation text outside the JSON):
        {{
            "title": "Provide a two word concise title for the analysis eg: 'Cross-sell Campaign' for a prompt 'Generate a follow-up email for customers who purchased the Logitech 4K Webcam, offering complementary accessories.'",
            "pre_evaluation": "use the evaluation definitions to evaluate the original prompt",
            "complexity_assessment": "simple or complex",
            "needs_refinement": "true or false",
            "refinement_reason": "detailed explanation of why refinement is or isn't needed",
            "refined_prompt": "optimized user prompt",
            "post_evaluation": "use the evaluation definitions to evaluate the refined prompt",
        }}
        """
        
        # Call the LLM with the full analysis instruction
        try:
            analysis_response = await self.call_llm(refinement_instruction, temperature=0.2)
            logger.info(f"LLM Analysis Response: {analysis_response}")
            analysis_json = self.extract_json_from_response(analysis_response)
            data = json.loads(analysis_json)
            
            # Extract adherence values for pre-evaluation
            pre_evaluation_result = data.get("pre_evaluation", {})
            post_evaluation_result = data.get("post_evaluation", {})
            title_result = data.get("title", "Simple Prompt")
            
            # Extract refined prompt (use original if refinement was not needed)
            needs_refinement = data.get("needs_refinement", "false").lower() == "true"
            refined_prompt = data.get("refined_prompt", prompt) if needs_refinement else prompt
            
            # Create and return the validation result with justifications
            return PromptValidationResult(
                title=title_result,
                original_prompt=prompt,
                refined_prompt=refined_prompt,
                pre_evaluation_result=pre_evaluation_result,
                post_evaluation_result=post_evaluation_result,
                complexity_assessment=data.get("complexity_assessment", "simple"),
                refinement_reason=data.get("refinement_reason", "No refinement needed")
            )
            
        except Exception as e:
            logger.error(f"Error during prompt analysis and refinement: {str(e)}")
            # Fallback to return original prompt in case of errors
            return PromptValidationResult(prompt, {"error": f"Analysis failed: {str(e)}"})