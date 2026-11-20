"""Rank stored person records from explicit name forms and independently supplied context."""
import re
import unicodedata

from rapidfuzz.distance import Levenshtein

from services import normalizer


def words(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(ch if ch.isalnum() or unicodedata.category(ch).startswith("M") else " " for ch in text).split()


def name_strength(form, query):
    tokens = words(form)
    if not tokens:
        return 0
    best = 0
    for start, word in enumerate(query):
        if word in tokens and len(word) >= 2:
            best = max(best, 52)
        if min(len(word), len(tokens[0])) >= 4 and Levenshtein.distance(word, tokens[0]) == 1:
            best = max(best, 43)
        window = query[start:start + len(tokens)]
        if len(window) != len(tokens):
            continue
        if window == tokens and len(tokens) > 1:
            best = max(best, 96 if all(len(t) > 1 for t in tokens) else 78)
        elif len(tokens) > 1 and any(len(w) > 1 and w == t for w, t in zip(window, tokens)):
            if all(w == t or (len(w) == 1 and t.startswith(w)) for w, t in zip(window, tokens)):
                best = max(best, 76)
            elif sum(Levenshtein.distance(w, t) for w, t in zip(window, tokens)) == 1:
                best = max(best, 81)
    return best


def rank_people(graph, documents, mention, context):
    nodes = {n["id"]: n for n in graph["nodes"]}
    adjacent = {}
    for edge in graph["edges"]:
        adjacent.setdefault(edge["source"], []).append(nodes[edge["target"]])
        adjacent.setdefault(edge["target"], []).append(nodes[edge["source"]])
    by_document = {}
    for node in nodes.values():
        if node["type"] in {"Crime", "Location", "Evidence", "PoliceStation"}:
            for source in node["sources"]:
                by_document.setdefault(source["doc_id"], set()).add((node["type"].lower(), node["name"]))
    q = words(mention)
    tokens = set(words(context))
    phrase = " " + " ".join(words(context)) + " "
    plates = set(normalizer.vehicles(context))
    candidates = []
    for person in nodes.values():
        if person["type"] != "Person":
            continue
        props = person["properties"]
        forms = [person["name"], *person["name"].split("@"), *props.get("aliases", [])]
        strength = max(name_strength(form, q) for form in forms)
        if not strength:
            continue
        fields = []
        for src in person["sources"]:
            fields.extend(sorted(by_document.get(src["doc_id"], set())))
            fields.append(("case", src["fir_number"]))
            fields.append(("station", documents.get(src["doc_id"], {}).get("police_station", "")))
        fields.extend((key, props.get(key, "")) for key in ("father_name", "address", "phone", "role"))
        fields.extend((n["type"].lower(), n["name"]) for n in adjacent.get(person["id"], []))
        reasons = {}
        for kind, value in fields:
            if not value:
                continue
            parts = words(value)
            if not parts:
                continue
            matches = " " + " ".join(parts) + " " in phrase
            if kind in {"crime", "evidence"}:
                informative = set(parts) - {"crime", "evidence", "item", "under", "the", "at", "of", "from"}
                matches |= any(len(t) >= 4 for t in informative & tokens)
            if kind in {"station", "policestation", "address", "location"}:
                significant = set(parts) - {"police", "station", "town", "ps", "road", "street", "district", "i"}
                matches |= bool(significant & tokens)
            if kind == "vehicle":
                matches |= bool(set(normalizer.vehicles(value)) & plates)
            if kind == "phone":
                matches = value in [normalizer.phone(m.group()) for m in normalizer.PHONE.finditer(context)]
            if matches:
                group = "station" if kind == "policestation" else kind
                reasons[group] = value
        weights = {"phone": 45, "case": 27, "father_name": 25, "vehicle": 22, "role": 4}
        bonus = sum(weights.get(k, 14) for k in reasons)
        # Reserve headroom for evidence that separates two identical full names.
        score = min(99, (84 if strength == 96 else strength) + bonus)
        candidates.append({
            "id": person["id"], "name": person["name"], "score": score, "strength": strength,
            "reasons": list(reasons.values()), "cases": sorted({s["fir_number"] for s in person["sources"]}),
            "stations": sorted({documents.get(s["doc_id"], {}).get("police_station", "") for s in person["sources"]} - {""}),
            "phone_match": "phone" in reasons,
        })
    return sorted(candidates, key=lambda row: (-row["score"], -row["strength"], row["name"], row["id"]))


def prompt_result(candidates, state, answer):
    return {
        "answer": answer, "candidates": candidates, "resolution": state, "citations": [],
        "matched_subgraph": {"nodes": [], "edges": []}, "cypher_executed": None,
        "top_k_chunks": [], "graph_mode": "none",
    }
