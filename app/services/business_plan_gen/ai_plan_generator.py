import re

from app.services.ai_core.ai_service import AIService


SECTION_PROMPTS = {
    "executive_summary": """
Write an investor-ready executive summary.

Business Idea:
{idea}

Industry: {industry}
Stage: {stage}
Target Market: {market}
""",

    "problem_solution": """
Describe the problem and solution.

Problem:
{problem}

Solution:
{solution}
""",

    "market_overview": """
Write a market overview.

Industry: {industry}
Target Market: {market}
""",

    "business_model": """
Explain the business model.

Revenue Model:
{revenue_model}
""",

    "operations": """
Describe operations.

Team:
{team}

Operations:
{operations}
""",

    "marketing": """
Write a marketing strategy.

Channels:
{channels}
""",

    "financial_narrative": """
Write a 3-year financial narrative.

Revenue assumptions:
{revenue}

Costs:
{costs}
"""
}




def strip_thinking(text: str) -> str:
    """
    Removes <think>...</think> blocks from LLM output
    """
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
def normalize_inputs(inputs: dict) -> dict:
    return {
        "idea": inputs.get("idea", ""),
        "industry": inputs.get("industry", ""),
        "stage": inputs.get("stage", ""),
        "market": inputs.get("market", ""),
        "problem": inputs.get("problem", ""),
        "solution": inputs.get("solution", ""),
        "revenue_model": inputs.get("revenue_model", "Subscription-based SaaS"),
        "pricing": inputs.get("pricing", "Tiered monthly pricing"),
        "revenue": inputs.get("revenue", "Recurring SaaS subscriptions with monthly growth"),
        "team": inputs.get("team", "Founding team with SaaS and AI experience"),
        "operations": inputs.get("operations", "Lean remote-first operations"),
        "channels": inputs.get("channels", "Content marketing, partnerships"),
        "costs": inputs.get("costs", "Cloud infrastructure, development, marketing")
    }


def generate_section(section_type, inputs, existing_content=None, action="generate"):

    prompt_template = SECTION_PROMPTS.get(section_type)

    if not prompt_template:
        raise ValueError("Invalid section type")

    inputs = normalize_inputs(inputs)

    base_prompt = prompt_template.format(**inputs)

    if action == "rewrite" and existing_content:
        base_prompt = f"Rewrite the following content professionally:\n\n{existing_content}"

    elif action == "expand" and existing_content:
        base_prompt = f"Expand the following content with more detail:\n\n{existing_content}"

    base_prompt = f"""
Generate a professional business plan section.

Rules:
- No illegal or unethical business practices
- No unrealistic financial guarantees
- Focus on practical startup advice

Request:
{base_prompt}
"""

    if len(base_prompt) > 5000:
        raise ValueError("Input too large")

    result = AIService.generate(
        feature="business_plan",
        user_input=base_prompt,
        temperature=0.6,
        max_tokens=1200
    )

    response_text = result.get("response", "")

    return strip_thinking(response_text)
