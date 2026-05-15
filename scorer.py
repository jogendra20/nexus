"""
scorer.py - Self-Learning Quality Scorer
Updates provider quality scores based on real outcomes.
Stolen from Ruflo, rebuilt in Python.
"""

import os
import json
from datetime import datetime

SCORES_FILE = "data/provider_scores.json"

DEFAULT_SCORES = {
    "github_models": {"reasoning": 10, "premium": 10, "coding": 9,  "trading": 7,  "search": 5,  "default": 8},
    "nvidia":        {"reasoning": 9,  "premium": 9,  "coding": 8,  "trading": 7,  "search": 5,  "default": 7},
    "cerebras":      {"reasoning": 6,  "premium": 5,  "coding": 6,  "trading": 9,  "search": 4,  "default": 8},
    "gemini":        {"reasoning": 8,  "premium": 8,  "coding": 7,  "trading": 8,  "search": 8,  "default": 8},
    "groq":          {"reasoning": 6,  "premium": 5,  "coding": 6,  "trading": 8,  "search": 5,  "default": 7},
    "mistral":       {"reasoning": 6,  "premium": 6,  "coding": 10, "trading": 5,  "search": 4,  "default": 6},
    "openrouter":    {"reasoning": 7,  "premium": 7,  "coding": 7,  "trading": 6,  "search": 5,  "default": 6},
    "huggingface":   {"reasoning": 7,  "premium": 6,  "coding": 7,  "trading": 5,  "search": 4,  "default": 6},
    "drona":         {"reasoning": 2,  "premium": 2,  "coding": 2,  "trading": 6,  "search": 10, "default": 3},
}

LEARNING_RATE  = 0.1   # how fast scores update
MIN_SCORE      = 1.0
MAX_SCORE      = 10.0

def load_scores() -> dict:
    os.makedirs("data", exist_ok=True)
    try:
        return json.load(open(SCORES_FILE))
    except:
        save_scores(DEFAULT_SCORES)
        return DEFAULT_SCORES

def save_scores(scores: dict):
    os.makedirs("data", exist_ok=True)
    json.dump(scores, open(SCORES_FILE, "w"), indent=2)

def update_score(provider: str, task: str, success: bool,
                 response_time_ms: int = 0, response_length: int = 0):
    scores = load_scores()

    if provider not in scores:
        scores[provider] = DEFAULT_SCORES.get(provider, {})
    if task not in scores[provider]:
        scores[provider][task] = 5.0

    current = scores[provider][task]

    # Outcome signal
    if success:
        outcome = 1.0
        # Speed bonus — faster is better (under 2s = full bonus)
        if response_time_ms > 0:
            speed_bonus = max(0, 1.0 - (response_time_ms / 10000))
            outcome += speed_bonus * 0.3
        # Length bonus — longer = more useful (up to 500 chars)
        if response_length > 0:
            length_bonus = min(response_length / 500, 1.0) * 0.2
            outcome += length_bonus
    else:
        outcome = -1.0  # penalize failures hard

    # Exponential moving average update
    new_score = current + LEARNING_RATE * (outcome * MAX_SCORE - current)
    new_score = max(MIN_SCORE, min(MAX_SCORE, new_score))

    scores[provider][task] = round(new_score, 3)
    save_scores(scores)

    print(f"[Scorer] {provider}/{task}: {current:.2f} → {new_score:.2f}")
    return new_score

def get_score(provider: str, task: str) -> float:
    scores = load_scores()
    return scores.get(provider, {}).get(task, 5.0)

def print_scores():
    scores = load_scores()
    print("\n[Scorer] Current quality scores:")
    for provider, tasks in scores.items():
        avg = sum(tasks.values()) / len(tasks)
        print(f"  {provider:15} avg={avg:.2f} | {tasks}")

if __name__ == "__main__":
    print_scores()
