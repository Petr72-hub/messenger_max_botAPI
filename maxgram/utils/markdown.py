"""Text helpers for the two markup dialects MAX accepts."""

from __future__ import annotations

import html as _html
import re

_MD_SPECIALS = re.compile(r"([\\`*_{}\[\]()#+\-.!|>~])")


def escape_md(text: str) -> str:
    """Escape every character that MAX's markdown parser treats as syntax."""
    return _MD_SPECIALS.sub(r"\\\1", text)


def escape_html(text: str) -> str:
    return _html.escape(text, quote=False)


# -- markdown ---------------------------------------------------------------


def bold(text: str) -> str:
    return f"**{text}**"


def italic(text: str) -> str:
    return f"*{text}*"


def code(text: str) -> str:
    return f"`{text}`"


def pre(text: str, language: str = "") -> str:
    return f"```{language}\n{text}\n```"


def strikethrough(text: str) -> str:
    return f"~~{text}~~"


def underline(text: str) -> str:
    return f"++{text}++"


def link(text: str, url: str) -> str:
    return f"[{text}]({url})"


# -- html -------------------------------------------------------------------


def hbold(text: str) -> str:
    return f"<b>{escape_html(text)}</b>"


def hitalic(text: str) -> str:
    return f"<i>{escape_html(text)}</i>"


def hcode(text: str) -> str:
    return f"<code>{escape_html(text)}</code>"


def hpre(text: str) -> str:
    return f"<pre>{escape_html(text)}</pre>"


def hlink(text: str, url: str) -> str:
    return f'<a href="{_html.escape(url, quote=True)}">{escape_html(text)}</a>'


def hstrikethrough(text: str) -> str:
    return f"<s>{escape_html(text)}</s>"


def hunderline(text: str) -> str:
    return f"<u>{escape_html(text)}</u>"


# -- misc -------------------------------------------------------------------


def text_join(*parts: str, sep: str = " ") -> str:
    return sep.join(p for p in parts if p)


TEXT_LIMIT = 4000


def split_text(text: str, limit: int = TEXT_LIMIT) -> list[str]:
    """Split a long post into chunks MAX will accept, preferring paragraph breaks."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    rest = text
    while len(rest) > limit:
        window = rest[:limit]
        cut = window.rfind("\n\n")
        if cut < limit // 2:
            cut = window.rfind("\n")
        if cut < limit // 2:
            cut = window.rfind(" ")
        if cut <= 0:
            cut = limit
        chunks.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    if rest:
        chunks.append(rest)
    return chunks
