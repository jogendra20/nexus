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
PERPLEXITY_TOKEN = os.getenv("PERPLEXITY_TOKEN")
POE_API_KEY = os.getenv("POE_API_KEY")
NVIDIA_KEY = os.getenv("NVIDIA_KEY")
CEREBRAS_KEY = os.getenv("CEREBRAS_KEY")
MISTRAL_KEY  = os.getenv("MISTRAL_KEY")
GITHUB_MODELS_KEY = os.getenv("GITHUB_MODELS_KEY")


# Provider rate limits
TASK_ROUTES = {
    "search":    ["drona", "gemini", "groq"],
    "coding":    ["mistral", "nvidia", "openrouter", "gemini", "groq"],
    "trading":   ["cerebras", "groq", "gemini", "nvidia"],
    "reasoning": ["nvidia", "github_models", "gemini", "openrouter", "groq"],
    "premium":   ["github_models", "nvidia", "gemini", "openrouter"],
    "default":   ["cerebras", "gemini", "github_models", "nvidia", "huggingface", "openrouter", "groq"],
} 

LIMITS = {
    "gemini":      {"calls": 60,  "period": 60},
    "openrouter":  {"calls": 20,  "period": 60},
    "poe":         {"calls": 10,  "period": 86400},
    "perplexity":  {"calls": 4,   "period": 86400},
    "drona":       {"calls": 100, "period": 86400},  # your own service
    "groq":        {"calls": 30,  "period": 60},
    "nvidia":      {"calls": 40, "period": 60},
    "cerebras":    {"calls": 30,  "period": 60},
    "mistral":     {"calls": 30,  "period": 60},
    "cerebras": {"calls": 30, "period": 60},
    "mistral":  {"calls": 30, "period": 60},
    "github_models":{"calls": 15,"period":60},
   "huggingface":   {"calls": 10, "period": 60},
}

# Keywords for auto classification
TASK_KEYWORDS = {
    "search":    ["search", "news", "latest", "today", "current", "find"],
    "coding":    ["code", "python", "debug", "build", "fix", "function", "script"],
    "reasoning": ["analyze", "explain", "reason", "compare", "think", "why"],
    "premium":   ["complex", "detailed", "deep", "thorough"],
}
