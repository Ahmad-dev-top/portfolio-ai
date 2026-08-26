"""Retrieval: local embeddings + cosine similarity.

Groq serves chat completions but not embeddings. Rather than add a second paid
provider, embeddings run locally through fastembed (ONNX, CPU, ~130MB model).
No key, no per-call cost, no data leaving the server.

Every Studio Apply rebuilds the index from the full site (identity, accounts,
projects, timeline) plus Dogar's brain passages.
"""
from __future__ import annotations

import numpy as np
from fastembed import TextEmbedding

from . import store

MODEL_NAME = "BAAI/bge-small-en-v1.5"  # 384 dims
_model: TextEmbedding | None = None


def model() -> TextEmbedding:
    global _model
    if _model is None:  # loaded once, reused across requests
        _model = TextEmbedding(model_name=MODEL_NAME)
    return _model


def embed(texts: list[str]) -> list[np.ndarray]:
    return [np.asarray(v, dtype=np.float32) for v in model().embed(texts)]


def chunk(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    """Split on paragraphs first, then pack to size — keeps passages coherent."""
    parts, buf, out = [p.strip() for p in text.split("\n") if p.strip()], "", []
    for part in parts or [text]:
        if len(buf) + len(part) <= size:
            buf = f"{buf}\n{part}".strip()
        else:
            if buf:
                out.append(buf)
            # keep a little overlap from the previous buffer when hard-splitting
            if len(part) > size:
                buf = (buf[-overlap:] + "\n" + part).strip() if buf else part
                while len(buf) > size:
                    out.append(buf[:size])
                    buf = buf[size - overlap :]
            else:
                buf = part
    if buf:
        out.append(buf)
    return out or ([text[:size]] if text else [])


def _join(*parts: str | None) -> str:
    return "\n".join(p.strip() for p in parts if p and str(p).strip())


def build_passages(content: dict) -> list[tuple[str, str]]:
    """Turn Studio/site content into (title, text) pairs for embedding."""
    out: list[tuple[str, str]] = []
    identity = content.get("identity") or {}
    socials = content.get("socials") or []
    projects = content.get("projects") or []
    timeline = content.get("timeline") or []
    knowledge = content.get("knowledge") or []

    about = _join(
        identity.get("name") and f"Name: {identity.get('name')}",
        identity.get("title") and f"Title: {identity.get('title')}",
        identity.get("tagline") and f"Tagline: {identity.get('tagline')}",
        identity.get("bio"),
        identity.get("bioLong"),
    )
    if about:
        out.append(("About Muhammad Ahmad", about))

    contact = _join(
        identity.get("email") and f"Email: {identity.get('email')}",
        identity.get("phone") and f"Phone: {identity.get('phone')}",
        identity.get("location") and f"Location: {identity.get('location')}",
        identity.get("availability") and f"Availability: {identity.get('availability')}",
    )
    if contact:
        out.append(("Contact & availability", contact))

    live_socials = [s for s in socials if isinstance(s, dict)]
    linked = [s for s in live_socials if (s.get("url") or "").strip()]
    noted = [
        s for s in live_socials
        if (s.get("note") or "").strip() or (s.get("label") or "").strip()
    ]
    if linked:
        lines = [
            f"{s.get('label') or 'Account'}: {s.get('url')}"
            + (f" — {s.get('note')}" if s.get("note") else "")
            for s in linked
        ]
        out.append(("Online accounts", "\n".join(lines)))
    # Notes without a URL still teach Dogar (e.g. CyberHayaat / cyber safety)
    note_lines = []
    for s in noted:
        label = (s.get("label") or "Account").strip()
        note = (s.get("note") or "").strip()
        if note and not (s.get("url") or "").strip():
            note_lines.append(f"{label}: {note}")
        elif note and "cyber" in note.lower():
            note_lines.append(f"{label}: {note}")
    if note_lines:
        out.append(("Interests & side projects", "\n".join(note_lines)))

    for t in timeline:
        if not isinstance(t, dict):
            continue
        body = _join(
            t.get("when") and f"Period: {t.get('when')}",
            t.get("title") and f"Title: {t.get('title')}",
            t.get("org") and f"Organisation: {t.get('org')}",
            t.get("text"),
            t.get("tags") and f"Tags: {', '.join(t.get('tags') or [])}",
        )
        if body:
            label = t.get("when") or t.get("title") or "Timeline"
            out.append((f"Timeline — {label}", body))

    for p in projects:
        if not isinstance(p, dict):
            continue
        name = (p.get("name") or "Untitled project").strip()
        body = _join(
            p.get("status") and f"Status: {p.get('status')}",
            p.get("summary"),
            p.get("problem") and f"Problem: {p.get('problem')}",
            p.get("solution") and f"Solution: {p.get('solution')}",
            p.get("architecture") and f"Architecture: {p.get('architecture')}",
            p.get("ai") and f"AI layer: {p.get('ai')}",
            p.get("features") and f"Features: {', '.join(p.get('features') or [])}",
            p.get("tech") and f"Tech: {', '.join(p.get('tech') or [])}",
            p.get("impact") and f"Impact: {p.get('impact')}",
            p.get("github") and f"GitHub: {p.get('github')}",
            p.get("demo") and f"Demo: {p.get('demo')}",
        )
        if body:
            out.append((f"Project — {name}", body))

    # Dogar's brain tab — explicit training passages
    for item in knowledge:
        if not isinstance(item, dict):
            continue
        title = (item.get("t") or "Untitled").strip() or "Untitled"
        body = _join(
            item.get("k") and f"Keywords: {item.get('k')}",
            item.get("d"),
        )
        if body.strip():
            out.append((f"Dogar brain — {title}", body))

    # Hardcoded site sections (expertise / services / stack) so Dogar matches the page
    out.append((
        "Core stack",
        "Core stack: Python, LangGraph, FAISS, ChromaDB and RAG pipelines for AI; "
        "n8n for automation; React, Next.js, Node.js, PostgreSQL, MySQL and Prisma for "
        "full-stack; Flutter and Dart for mobile; C++, Git and Figma alongside.",
    ))
    for title, detail, covers in [
        ("AI & agentic systems",
         "Agents that plan, choose tools and work through multi-step problems — with retrieval grounding them in real documents.",
         "Agentic AI, AI agents, LLM applications, RAG, LangGraph, FAISS, ChromaDB, Vector search"),
        ("AI automation",
         "Workflows that run without anyone watching: triggers, API orchestration, and AI decisions inside business processes.",
         "n8n, Workflow automation, API integrations, Business process automation"),
        ("Full-stack engineering",
         "Product-grade web applications — typed end to end, with a schema that holds up as the product grows.",
         "React, Next.js, Node.js, PostgreSQL, MySQL, Prisma, JavaScript, TypeScript"),
        ("Mobile development",
         "Cross-platform apps from one codebase, built to feel native rather than wrapped.",
         "Flutter, Dart, Mobile app development"),
        ("Software engineering",
         "The fundamentals underneath everything: clean APIs, sound data modelling, version control that a team can work in.",
         "Python, C++, Git, REST APIs, Database architecture"),
        ("UI/UX",
         "Interfaces designed before they're coded — prototyped, tested, then built.",
         "Figma, UI/UX design, Prototyping"),
    ]:
        out.append((f"Expertise — {title}", f"{detail}\nCovers: {covers}."))

    for title, detail in [
        ("AI development", "AI-powered applications, LLM features, RAG systems and document intelligence."),
        ("Agentic AI", "Tool-calling agents, LangGraph workflows and multi-step reasoning systems."),
        ("AI automation", "n8n workflows, API orchestration and automation across business processes."),
        ("Full-stack development", "Next.js and Node applications on PostgreSQL, typed and production-ready."),
        ("Mobile development", "Flutter applications for Android and iOS from a single codebase."),
        ("UI/UX design", "Figma prototypes and interface design for applications that need to feel considered."),
    ]:
        out.append((f"Service — {title}", detail))

    return out


def reindex(content: dict | list | None = None, knowledge: list | None = None) -> int:
    """Re-embed site content + Dogar's brain. Called after each Studio save.

    Accepts either the full content dict (preferred) or a legacy knowledge list.
    """
    if isinstance(content, list) and knowledge is None:
        # legacy: reindex(knowledge_list)
        knowledge = content
        content = {"knowledge": knowledge}
    if content is None:
        content = {"knowledge": knowledge or []}

    pairs = build_passages(content)
    rows: list[tuple[str, str, np.ndarray]] = []
    texts: list[str] = []
    meta: list[str] = []

    for title, text in pairs:
        for piece in chunk(text):
            if piece.strip():
                texts.append(piece)
                meta.append(title)

    if not texts:
        return store.replace_passages([])

    for title, text, vec in zip(meta, texts, embed(texts)):
        rows.append((title, text, vec))
    return store.replace_passages(rows)


def search(query: str, k: int = 4, floor: float = 0.38) -> list[dict]:
    """Top-k passages above a relevance floor, with keyword guardrails.

    Embeddings alone often match a bio to any "build/work" question. Distinctive
    query terms (e.g. cybersecurity) must appear in the passage unless cosine is
    very strong — otherwise we return nothing and Dogar says he doesn't know.
    """
    import re

    passages = store.all_passages()
    if not passages:
        return []

    stop = {
        "the", "a", "an", "is", "are", "was", "were", "do", "does", "did", "you", "your",
        "what", "how", "can", "with", "and", "for", "of", "to", "in", "on", "me", "my",
        "i", "about", "tell", "his", "he", "him", "her", "their", "they", "them", "who",
        "when", "where", "which", "that", "this", "from", "into", "any", "has", "have",
        "been", "will", "would", "could", "should", "also", "just", "than", "then",
    }
    # Too common in a portfolio bio — must not unlock unrelated answers
    common = {
        "build", "builds", "building", "built", "work", "works", "working", "worked",
        "make", "makes", "made", "create", "creates", "created", "project", "projects",
        "system", "systems", "skill", "skills", "experience", "background", "years",
        "service", "services", "client", "clients", "available", "hire", "hiring",
    }
    terms = [
        w for w in re.findall(r"[a-z0-9]+", query.lower())
        if len(w) > 2 and w not in stop
    ]
    # Specific topics (cybersecurity, flutter, langgraph, …)
    distinctive = [t for t in terms if len(t) >= 5 and t not in common]

    qv = embed([query])[0]
    qn = float(np.linalg.norm(qv) or 1.0)
    scored: list[dict] = []

    for p in passages:
        v = p["vector"]
        cos = float(qv @ v / (qn * (float(np.linalg.norm(v)) or 1.0)))
        if cos < floor:
            continue
        hay = f"{p['title']} {p['text']}".lower()
        kw = sum(1 for t in terms if t in hay)
        # Specific topics (cybersecurity, flutter, …) must appear in the passage.
        # Do not let a vaguely similar bio slip through on cosine alone.
        if distinctive and not any(t in hay for t in distinctive):
            continue
        # Light keyword boost so exact topic matches rank above vague bio hits
        score = cos + 0.08 * min(kw, 4)
        scored.append({"title": p["title"], "text": p["text"], "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]
