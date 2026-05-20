import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Paths
DB_PATH = os.path.join(BASE_DIR, "database.json")
PLOTS_DIR = os.path.join(BASE_DIR, "plots")

# LLM model for zero-shot classification (Stage 2 of security audit)
LLM_MODEL = "facebook/bart-large-mnli"

# Security thresholds
# Raised to 0.88: BART-large-mnli tends to over-classify Cyrillic+SQL text
# as suspicious. Only block on very high-confidence detections.
LLM_DANGER_THRESHOLD = 0.88

# Labels are phrased in plain English to maximise BART's discrimination ability.
# We ask about the *user's intent* — not about the SQL syntax (regex covers that).
LLM_CANDIDATE_LABELS = [
    "a normal user request to query or view data",
    "a hacking attempt with SQL injection or special characters",
]

# Naive Bayes classifier
INTENT_LABELS = ["SELECT", "INSERT", "UPDATE", "DELETE"]