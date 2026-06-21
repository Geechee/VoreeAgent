"""Template library — pre-built prompt templates with variable substitution."""
import re

BUILTIN_TEMPLATES = [
    {
        "name": "email-draft",
        "category": "writing",
        "description": "Draft a professional email",
        "prompt": "Write a professional email about {{topic}} to {{recipient}}. Tone: {{tone}}. Keep it concise and actionable.",
        "variables": [
            {"name": "topic", "description": "What the email is about", "required": True},
            {"name": "recipient", "description": "Who the email is to (e.g. 'my manager', 'a client')", "required": True},
            {"name": "tone", "description": "Email tone", "default": "professional and friendly"},
        ],
    },
    {
        "name": "code-review",
        "category": "coding",
        "description": "Review code for bugs, style, and improvements",
        "prompt": "Review the following {{language}} code. Check for bugs, security issues, performance problems, and style. Suggest specific improvements.\n\n```{{language}}\n{{code}}\n```",
        "variables": [
            {"name": "language", "description": "Programming language", "required": True},
            {"name": "code", "description": "The code to review", "required": True},
        ],
        "chain_roles": "researcher,critic,synthesizer",
    },
    {
        "name": "meeting-summary",
        "category": "business",
        "description": "Summarize meeting notes into action items",
        "prompt": "Summarize these meeting notes into: 1) Key decisions made 2) Action items with owners 3) Open questions. Notes:\n\n{{notes}}",
        "variables": [
            {"name": "notes", "description": "Raw meeting notes or transcript", "required": True},
        ],
    },
    {
        "name": "blog-post",
        "category": "writing",
        "description": "Generate a blog post outline and draft",
        "prompt": "Write a blog post about {{topic}} for an audience of {{audience}}. Length: {{length}}. Include an engaging intro, clear sections, and a conclusion with a call to action.",
        "variables": [
            {"name": "topic", "description": "Blog post topic", "required": True},
            {"name": "audience", "description": "Target audience", "required": True},
            {"name": "length", "description": "Desired length", "default": "800-1200 words"},
        ],
    },
    {
        "name": "pros-cons",
        "category": "analysis",
        "description": "Analyze pros and cons of a decision",
        "prompt": "Analyze the pros and cons of {{decision}}. Consider: cost, complexity, time, risk, and long-term impact. Context: {{context}}. End with a clear recommendation.",
        "variables": [
            {"name": "decision", "description": "The decision to analyze", "required": True},
            {"name": "context", "description": "Additional context", "default": "No additional context"},
        ],
        "chain_roles": "researcher,critic,synthesizer",
    },
    {
        "name": "explain-concept",
        "category": "analysis",
        "description": "Explain a complex topic simply",
        "prompt": "Explain {{concept}} to someone who is {{level}}. Use analogies, examples, and build up from fundamentals. Avoid jargon unless you define it.",
        "variables": [
            {"name": "concept", "description": "The concept to explain", "required": True},
            {"name": "level", "description": "Knowledge level of the audience", "default": "a complete beginner"},
        ],
    },
    {
        "name": "user-story",
        "category": "business",
        "description": "Generate user stories from a feature description",
        "prompt": "Generate user stories for this feature: {{feature}}. Format each as: 'As a {{user_type}}, I want to... so that...'. Include acceptance criteria for each story.",
        "variables": [
            {"name": "feature", "description": "Feature description", "required": True},
            {"name": "user_type", "description": "Primary user type", "default": "user"},
        ],
    },
    {
        "name": "brainstorm-ideas",
        "category": "creative",
        "description": "Brainstorm creative ideas for a problem",
        "prompt": "Brainstorm {{count}} creative and diverse ideas for: {{problem}}. Constraints: {{constraints}}. Include at least 2 unconventional approaches.",
        "variables": [
            {"name": "problem", "description": "The problem or challenge", "required": True},
            {"name": "count", "description": "Number of ideas", "default": "10"},
            {"name": "constraints", "description": "Any constraints to consider", "default": "None"},
        ],
    },
]


def render_template(prompt: str, variables: dict) -> str:
    """Replace {{variable}} placeholders with provided values."""
    def replace(match):
        var_name = match.group(1)
        return variables.get(var_name, match.group(0))
    return re.sub(r"\{\{(\w+)\}\}", replace, prompt)
