import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_KEY      = os.getenv("GEMINI_KEY")
OPENROUTER_KEY  = os.getenv("OPENROUTER_KEY")
POE_TOKEN       = os.getenv("POE_TOKEN")
SUPABASE_URL    = os.getenv("SUPABASE_URL")
SUPABASE_KEY    = os.getenv("SUPABASE_KEY")
GROQ_KEY    = os.getenv("GROQ_KEY")
DRONA_URL   = os.getenv("DRONA_URL")  # your Render URL
DRONA_PASSWORD = os.getenv("DRONA_PASSWORD")

# Provider rate limits
TASK_ROUTES = {
    "search":    ["perplexity", "drona", "gemini", "groq"],
    "coding":    ["openrouter", "gemini", "groq"],
    "reasoning": ["gemini", "poe", "groq"],
    "premium":   ["poe", "gemini", "groq"],
    "default":   ["gemini", "openrouter", "groq"],
}

LIMITS = {
    "gemini":      {"calls": 60,  "period": 60},
    "openrouter":  {"calls": 20,  "period": 60},
    "poe":         {"calls": 10,  "period": 86400},
    "perplexity":  {"calls": 4,   "period": 86400},
    "drona":       {"calls": 100, "period": 86400},  # your own service
    "groq":        {"calls": 30,  "period": 60},
}

# Keywords for auto classification
TASK_KEYWORDS = {
    "search":    ["search", "news", "latest", "today", "current", "find"],
    "coding":    ["code", "python", "debug", "build", "fix", "function", "script"],
    "reasoning": ["analyze", "explain", "reason", "compare", "think", "why"],
    "premium":   ["complex", "detailed", "deep", "thorough"],
}
