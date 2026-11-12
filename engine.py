"""Rule based task update interpreter for the coordinator MVP."""
from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class Decision:
    status: str
    blocker: str | None = None
    confidence: float = 0.0
    reason: str = ""


_BLOCKED_PATTERNS = (
    r"\b(?:waiting for|wait(?:ing)? on|blocked by|blocked on|need|needs|awaiting)\s+(?:the\s+)?(.+)",
    r"\b(?:can't|cannot|unable to|stuck without)\s+(?:continue|proceed|finish|move forward)\s+(?:until|without)\s+(.+)",
    r"(?<=,)\s*(.+?)\s+ka\s+wait\b",
    r"\bmujhe\s+(.+?)\s+ka\s+wait\b",
    r"(?<=,)\s*(.+?)\s+nahi\s+(?:mila|mili|milay|मिला|मिली)\b",
    r"\bmujhe\s+(.+?)\s+nahi\s+(?:mila|mili|milay|मिला|मिली)\b",
)
_COMPLETE = re.compile(r"\b(done|completed|complete|finished|shipped|merged|submitted|resolved)\b", re.I)
_VAGUE = re.compile(r"\b(?:working on it|in progress|soon|will do|started|okay|ok|noted|looking into it|dekh raha|kar raha|will update)\b", re.I)
_NEGATION = re.compile(r"\b(?:not|isn't|isnt|wasn't|wasnt|no longer|not yet|nahi)\b", re.I)


def _clean_blocker(value: str) -> str:
    value = re.sub(r"[.!?,;]+$", "", value.strip())
    value = re.sub(r"^(?:the|a|an)\s+", "", value, flags=re.I)
    value = re.sub(r"\s+", " ", value)
    return value[:100].strip()


def analyze_update(message: str) -> Decision:
    """Classify a reply conservatively; blockers take precedence over completion."""
    text = message.strip()
    if not text:
        return Decision("Needs Clarification", confidence=0.0, reason="Empty reply")
    low = text.lower()
    for pattern in _BLOCKED_PATTERNS:
        match = re.search(pattern, low, re.I)
        if match:
            blocker = _clean_blocker(match.group(1))
            # Remove trailing status/comment clauses from the captured blocker.
            blocker = re.split(r"\b(?:but|and|so|because)\b", blocker, maxsplit=1, flags=re.I)[0].strip()
            if blocker:
                return Decision("Blocked", blocker, 0.94, "Reply explicitly says progress depends on an unmet requirement")
    # A positive completion claim is accepted only when not negated and no blocker was found.
    if _COMPLETE.search(low) and not _NEGATION.search(low):
        return Decision("Complete", confidence=0.91, reason="Clear completion language")
    if _VAGUE.search(low):
        return Decision("In Progress", confidence=0.76, reason="Reply indicates work is underway but gives no completion evidence")
    return Decision("Needs Clarification", confidence=0.42, reason="Reply does not clearly establish completion or a blocker")


def analyze_multi_task_reply(message: str, task_titles: Iterable[str]) -> list[tuple[str, Decision]]:
    """Analyze newline/semicolon separated updates against explicitly named tasks.

    If a reply contains one update and multiple tasks, it is intentionally returned
    once for each task as an unassigned/ambiguous decision rather than guessing.
    """
    titles = list(task_titles)
    chunks = [part.strip(" -\t") for part in re.split(r"[\n;]+", message) if part.strip()]
    if not chunks:
        return [(title, analyze_update("")) for title in titles]
    out: list[tuple[str, Decision]] = []
    if len(chunks) == 1 and len(titles) > 1:
        return [(title, Decision("Needs Clarification", confidence=0.3, reason="One update may refer to multiple tasks")) for title in titles]
    for i, title in enumerate(titles):
        # Prefer a chunk containing the task title; otherwise use positional mapping only
        # when counts match. This prevents a reply about task A completing task B.
        matched = next((c for c in chunks if title.lower() in c.lower()), None)
        if matched is None and len(chunks) == len(titles):
            matched = chunks[i]
        out.append((title, analyze_update(matched or "")))
    return out
