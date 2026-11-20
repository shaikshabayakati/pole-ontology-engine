"""Fuse dense neighbours with corpus-weighted lexical ranks on the original source spans."""
import math
import re
from collections import Counter

from services import embedder, normalizer

STOP = set("a an and are as at be by do does for from how in is it me of on or show that the to what which who with".split())


def tokens(text):
    terms = re.findall(r"[^\W_]+", text.casefold())
    terms.extend(p.casefold() for p in normalizer.vehicles(text))
    terms.extend(normalizer.fir_number(m.group()).casefold() for m in normalizer.FIR.finditer(text))
    return [t for t in terms if t not in STOP]


def retrieve(store, question, spans=None):
    with store.lock:
        corpus = list(store.chunks.values())
    if spans is not None:
        corpus = [c for c in corpus if any(
            c["doc_id"] == s["doc_id"] and c["page_number"] == s["page_number"]
            and c["line_start"] <= s["line_end"] and c["line_end"] >= s["line_start"] for s in spans)]
    if not corpus:
        return []
    vector = embedder.embed_text(question)
    if spans is None:
        dense = store.vector_search(vector, embedder.mode(), limit=25)
    else:
        import numpy as np
        dense = sorted(({"chunk_id": c["chunk_id"], "score": float(np.dot(vector, c["embedding"]))}
                        for c in corpus if c.get("embedding_model") == embedder.mode()),
                       key=lambda c: -c["score"])[:25]
    dense_scores = {c["chunk_id"]: c["score"] for c in dense}
    dense_rank = {c["chunk_id"]: i for i, c in enumerate(dense, 1) if c["score"] >= 0.18}
    q = set(tokens(question))
    counts = [Counter(tokens(c["text"] + " " + c["fir_number"])) for c in corpus]
    df = Counter(t for count in counts for t in q & count.keys())
    n = len(corpus)
    avg = sum(c.total() for c in counts) / n or 1
    ranks = []
    for row, count in zip(corpus, counts):
        score = sum(math.log1p((n - df[t] + 0.5) / (df[t] + 0.5)) * count[t] * 2.2 /
                    (count[t] + 1.2 * (0.25 + 0.75 * count.total() / avg)) for t in q & count.keys())
        if score:
            ranks.append((score, row["chunk_id"]))
    lexical_rank = {key: i for i, (_, key) in enumerate(sorted(ranks, reverse=True), 1)}
    fused = []
    for row in corpus:
        key = row["chunk_id"]
        score = sum(weight / (10 + ranking[key]) for ranking, weight in ((dense_rank, 1), (lexical_rank, 1.15)) if key in ranking)
        if score:
            fused.append((score, key, row))
    results = []
    for score, key, row in sorted(fused, reverse=True):
        if any(r["doc_id"] == row["doc_id"] and r["page_number"] == row["page_number"]
               and r["text"].strip() == row["text"].strip() for r in results):
            continue
        results.append({**{k: v for k, v in row.items() if k != "embedding"},
                        "score": score, "cosine": dense_scores.get(key)})
        if len(results) == 5:
            break
    return results
