"""
Wikipedia Agent

Agent that uses Wikipedia API tools to answer questions.
"""

import os
import re
import unicodedata
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent
from tools import search_wikipedia, get_wikipedia_page

# Load .env file if it exists
# Try loading from wikiagent directory, parent directory, or project root
env_paths = [
    Path(__file__).parent / '.env',                    # capstone_project/wikiagent/.env
    Path(__file__).parent.parent / '.env',              # capstone_project/.env
    Path(__file__).parent.parent.parent / '.env',       # project root/.env
]

for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path, override=True)
        break
else:
    # If no .env found, try loading from default location (current directory)
    load_dotenv(override=True)


# Guardrail structure
class CapybaraGuardrail(BaseModel):
    """Guardrail result indicating if the question is about capybaras."""
    reasoning: str
    fail: bool
    sanitized_input: str = ""
    security_flags: list[str] = []


# Security patterns for prompt injection detection
PROMPT_INJECTION_PATTERNS = [
    r"(?i)ignore\s+(your\s+)?(previous|prior|earlier|above|all)\s+(instructions?|prompts?|directives?)",
    r"(?i)you\s+are\s+now\s+(in\s+)?(dan|jailbreak|developer|unrestricted)\s+mode",
    r"(?i)forget\s+(your\s+)?(instructions?|prompts?|directives?)",
    r"(?i)disregard\s+(your\s+)?(previous|prior|earlier|above)\s+(instructions?|prompts?)",
    r"(?i)override\s+(your\s+)?(instructions?|prompts?|directives?)",
    r"(?i)system\s*:\s*",
    r"(?i)assistant\s*:\s*",
    r"(?i)user\s*:\s*",
    r"(?i)new\s+(instructions?|prompts?|directives?)",
    r"(?i)act\s+as\s+(if\s+)?(you\s+are\s+)?(a|an)\s+",
    r"(?i)pretend\s+(to\s+be|you\s+are|that\s+you)",
    r"(?i)roleplay\s+(as|that\s+you)",
    r"(?i)simulate\s+(being|that\s+you)",
]

# Maximum input length (characters) - prevent DOS attacks
MAX_INPUT_LENGTH = 5000


def sanitize_input(message: str) -> tuple[str, list[str]]:
    """
    Sanitize and preprocess user input to detect and neutralize attack attempts.
    
    Args:
        message: Raw user input
        
    Returns:
        Tuple of (sanitized_message, security_flags)
    """
    security_flags = []
    sanitized = message
    
    # 1. Check input length
    if len(sanitized) > MAX_INPUT_LENGTH:
        security_flags.append(f"Input length exceeds maximum ({len(sanitized)} > {MAX_INPUT_LENGTH})")
        sanitized = sanitized[:MAX_INPUT_LENGTH]
        security_flags.append("Input truncated to maximum length")
    
    # 2. Normalize to UTF-8 and remove Unicode tricks
    try:
        # Normalize Unicode (NFKC: Compatibility Decomposition, followed by Canonical Composition)
        sanitized = unicodedata.normalize('NFKC', sanitized)
        
        # Remove zero-width characters
        zero_width_chars = [
            '\u200b',  # Zero-width space
            '\u200c',  # Zero-width non-joiner
            '\u200d',  # Zero-width joiner
            '\u2060',  # Word joiner
            '\ufeff',  # Zero-width no-break space
            '\u180e',  # Mongolian vowel separator
        ]
        for char in zero_width_chars:
            if char in sanitized:
                security_flags.append(f"Removed zero-width character: {repr(char)}")
                sanitized = sanitized.replace(char, '')
        
        # Detect and flag homoglyphs (similar-looking characters)
        # Common homoglyph patterns
        homoglyph_patterns = [
            (r'[а-я]', 'Cyrillic characters detected'),
            (r'[α-ω]', 'Greek letters detected'),
        ]
        for pattern, description in homoglyph_patterns:
            if re.search(pattern, sanitized):
                security_flags.append(description)
        
    except Exception as e:
        security_flags.append(f"Unicode normalization error: {str(e)}")
    
    # 3. Detect and flag prompt injection attempts
    for pattern in PROMPT_INJECTION_PATTERNS:
        matches = re.findall(pattern, sanitized)
        if matches:
            security_flags.append(f"Potential prompt injection detected: {pattern[:50]}...")
            # Remove the injection attempt
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
    
    # 4. Remove HTML/XML tags
    html_xml_pattern = r'<[^>]+>'
    html_matches = re.findall(html_xml_pattern, sanitized)
    if html_matches:
        security_flags.append(f"Removed {len(html_matches)} HTML/XML tag(s)")
        sanitized = re.sub(html_xml_pattern, '', sanitized)
    
    # 5. Detect and remove JavaScript code
    js_patterns = [
        r'<script[^>]*>.*?</script>',  # <script> tags
        r'javascript:',  # javascript: protocol
        r'on\w+\s*=',  # Event handlers like onclick=
        r'eval\s*\(',  # eval() calls
        r'document\.',  # DOM manipulation
        r'window\.',  # Window object
    ]
    for pattern in js_patterns:
        matches = re.findall(pattern, sanitized, re.IGNORECASE | re.DOTALL)
        if matches:
            security_flags.append(f"JavaScript code detected and removed: {pattern[:30]}...")
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
    
    # 6. Detect and remove SQL-like syntax (basic detection)
    sql_patterns = [
        r'(?i)(union|select|insert|update|delete|drop|create|alter|exec|execute)\s+',
        r'(?i)(or|and)\s+\d+\s*=\s*\d+',  # SQL injection: OR 1=1
        r'(?i);\s*(drop|delete|update|insert)',  # SQL command chaining
    ]
    for pattern in sql_patterns:
        matches = re.findall(pattern, sanitized)
        if matches:
            security_flags.append(f"SQL-like syntax detected and removed: {pattern[:30]}...")
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
    
    # 7. Remove excessive whitespace and normalize
    sanitized = re.sub(r'\s+', ' ', sanitized)  # Multiple spaces to single space
    sanitized = sanitized.strip()
    
    return sanitized, security_flags


def capybara_guardrail(message: str) -> CapybaraGuardrail:
    """
    IMPORTANT: USE THIS FUNCTION TO VALIDATE THE USER INPUT BEFORE PROCESSING.
    STOP THE EXECUTION IF THE GUARDRAIL TRIGGERS.

    This function performs input sanitization and checks if the user message is about capybaras.
    If the question is not about capybaras or contains security threats, the guardrail will fail.
    
    Args:
        message: The user input message/question
        
    Returns:
        CapybaraGuardrail indicating if the question is safe and about capybaras
    """
    # Step 1: Sanitize input and detect security threats
    sanitized, security_flags = sanitize_input(message)
    
    # If input was heavily modified or contains serious security flags, fail
    if security_flags:
        # Check for critical security issues
        critical_flags = [f for f in security_flags if any(
            keyword in f.lower() for keyword in ['injection', 'javascript', 'sql', 'exceeds maximum']
        )]
        
        if critical_flags:
            return CapybaraGuardrail(
                reasoning=f'Security threat detected: {"; ".join(critical_flags[:3])}. Input rejected.',
                fail=True,
                sanitized_input=sanitized,
                security_flags=security_flags
            )
    
    # Step 2: Check if sanitized input is about capybaras
    message_lower = sanitized.lower()
    
    # Keywords that indicate the question is about capybaras
    capybara_keywords = [
        "capybara",
        "capybaras",
        "hydrochoerus",
        "greater capybara",
        "lesser capybara"
    ]
    
    # Check if any capybara-related keyword is in the sanitized message
    for keyword in capybara_keywords:
        if keyword in message_lower:
            reasoning = f'Question is about capybaras (contains: {keyword})'
            if security_flags:
                reasoning += f'. Security flags: {"; ".join(security_flags[:2])}'
            return CapybaraGuardrail(
                reasoning=reasoning,
                fail=False,
                sanitized_input=sanitized,
                security_flags=security_flags
            )
    
    # If no capybara keywords found, guardrail fails
    reasoning = 'Question is not about capybaras. This agent only answers questions about capybaras.'
    if security_flags:
        reasoning += f' Security flags: {"; ".join(security_flags[:2])}'
    
    return CapybaraGuardrail(
        reasoning=reasoning,
        fail=True,
        sanitized_input=sanitized,
        security_flags=security_flags
    )


# Agent instructions
wikipedia_agent_instructions = """
You are a helpful Wikipedia research assistant that specializes in answering questions about capybaras.

IMPORTANT: USE THE GUARDRAIL FUNCTION TO VALIDATE THE USER INPUT BEFORE PROCESSING.
STOP THE EXECUTION IF THE GUARDRAIL TRIGGERS (fail=True).

Your workflow when answering questions:
1. FIRST, use capybara_guardrail(message) to validate the question is about capybaras
2. If the guardrail fails (fail=True), STOP immediately and inform the user that you only answer questions about capybaras
3. If the guardrail passes (fail=False), proceed with:
   a. Use search_wikipedia(query) to find relevant Wikipedia pages
   b. Review the search results to identify the most relevant pages
   c. Use get_wikipedia_page(title) to retrieve the content of the most relevant pages
   d. Analyze the page content to answer the user's question
   e. ALWAYS include references/citations in your answer

IMPORTANT GUIDELINES:
- ALWAYS call capybara_guardrail FIRST before doing anything else
- If capybara_guardrail returns fail=True, STOP and tell the user you only answer capybara questions
- Always start with a search - never try to answer without searching first
- Use specific search terms that match what the user is asking about
- Read multiple relevant pages if needed to provide a comprehensive answer
- When you get page content, look for specific information that answers the question
- MANDATORY: You MUST cite your sources by including references to the Wikipedia pages you used
- Format references as: [Page Title](https://en.wikipedia.org/wiki/Page_Title) or as a list at the end
- Always include at least one reference/citation in your answer
- If search returns no results, try alternative search terms
- If a page is not found, try variations of the title or search again
"""

# Create the agent
wikipedia_agent = Agent(
    name='wikipedia_agent',
    instructions=wikipedia_agent_instructions,
    tools=[capybara_guardrail, search_wikipedia, get_wikipedia_page],
    model='openai:gpt-4o-mini'
)

