import re

import jellyfish
from metaphone import doublemetaphone
from rapidfuzz import fuzz

from services.normalizer import phone

TITLES = {"mr", "mrs", "ms", "shri", "smt"}
SHORT_NAMES = {"md": "mohammed", "mohammad": "mohammed", "mohamed": "mohammed"}


def canonical_name(name: str) -> str:
    words = re.findall(r"[^\W\d_]+", name.casefold().split("@", 1)[0])
    return " ".join(SHORT_NAMES.get(word, word) for word in words if word not in TITLES)


def phonetic_match(left: str, right: str) -> bool:
    left_codes = set(doublemetaphone(left)) - {""}
    right_codes = set(doublemetaphone(right)) - {""}
    return bool(left_codes & right_codes) or (
        bool(jellyfish.metaphone(left)) and jellyfish.metaphone(left) == jellyfish.metaphone(right)
    )


def score_pair(source: dict, target: dict) -> tuple[float, str]:
    left, right = source["properties"], target["properties"]
    if source["type"] == "Vehicle":
        exact = bool(left.get("reg_no") and left.get("reg_no") == right.get("reg_no"))
        return (1.0, "Identical normalized registration") if exact else (0.0, "")
    left_phone, right_phone = phone(str(left.get("phone", ""))), phone(str(right.get("phone", "")))
    if left_phone and right_phone:
        return (1.0, "Identical normalized mobile number") if left_phone == right_phone else (0.0, "")
    a, b = canonical_name(source["name"]), canonical_name(target["name"])
    if min(len(a), len(b)) < 3:
        return 0.0, ""
    name_score = fuzz.token_sort_ratio(a, b) / 100
    sound = phonetic_match(a, b)
    father_a = canonical_name(str(left.get("father_name", "")))
    father_b = canonical_name(str(right.get("father_name", "")))
    father_score = fuzz.ratio(father_a, father_b) / 100 if father_a and father_b else None
    if father_score is not None and father_score < 0.65:
        return 0.0, ""
    father_sound = bool(father_score is not None and phonetic_match(father_a, father_b))
    value = 0.82 * name_score + 0.06 * sound + 0.05 * (father_score or 0) + 0.02 * father_sound
    alias_a = {canonical_name(alias) for alias in left.get("aliases", []) if alias}
    alias_b = {canonical_name(alias) for alias in right.get("aliases", []) if alias}
    shared_alias = any(len(alias) >= 3 for alias in (alias_a & alias_b) | (alias_a & {b}) | (alias_b & {a}))
    if a == b and (father_score == 1 or shared_alias):
        value = max(value, 0.96)
    if shared_alias:
        value = max(value, 0.95 if a == b else 0.82)
    if name_score < 0.95 and not (father_score == 1 and sound):
        value = min(value, 0.919)
    father_note = f"{father_score:.0%} similarity" if father_score is not None else "missing"
    reason = f"Name {name_score:.0%} · phonetics {'match' if sound else 'differ'} · father name {father_note}"
    return value, reason + (" · shared alias" if shared_alias else "")
