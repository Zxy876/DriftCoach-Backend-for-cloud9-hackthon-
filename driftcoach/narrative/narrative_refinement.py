from __future__ import annotations

from typing import List


def _polish_line(line: str) -> str:
    if not line.strip().startswith("-"):
        return line
    text = line[1:].strip()
    # Coach-style leading verbs
    replacements = [
        ("建议", "建议"),
        ("需要", "建议"),
    ]
    for old, new in replacements:
        if text.startswith(old):
            text = f"{new}{text[len(old):]}"
            break
    # soften generic labels
    text = text.replace("暂无明确证据", "当前样本有限，结论需在会议中确认")
    return f"- {text}"


def refine_narrative(content: str, narrative_type: str) -> str:
    """Lightweight refinement: smooth fact→impact phrasing and coach tone.
    No new mining/rules/models.
    """
    lines: List[str] = content.split("\n")
    refined: List[str] = []
    for ln in lines:
        if ln.strip().startswith("-"):
            refined.append(_polish_line(ln))
        else:
            refined.append(ln)
    return "\n".join(refined)
