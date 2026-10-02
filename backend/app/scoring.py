import re

RULES = [
    ("urgent language", re.compile(r"\b(urgent|immediately|act now|final notice)\b", re.I), 20),
    ("credential request", re.compile(r"\b(password|passcode|one[- ]?time code|otp|ssn|social security)\b", re.I), 25),
    ("payment request", re.compile(r"\b(gift card|wire transfer|bitcoin|crypto|send money|payment)\b", re.I), 25),
    ("suspicious link", re.compile(r"https?://[^\s]+", re.I), 15),
    ("impersonation", re.compile(r"\b(bank|irs|police|microsoft|support team)\b", re.I), 10),
]


def analyze(content: str) -> tuple[int, str, list[str]]:
    score = 0
    flags = []
    for name, pattern, weight in RULES:
        if pattern.search(content):
            flags.append(name)
            score += weight
    score = min(score, 100)
    verdict = "high-risk" if score >= 60 else "suspicious" if score >= 30 else "low-risk"
    return score, verdict, flags
