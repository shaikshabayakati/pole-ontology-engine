import re

PLATE = re.compile(r"\b([A-Z]{2})[ -]*(\d{1,2})[ -]*([A-Z]{1,3})[ -]*(\d{4})\b", re.I)
PHONE = re.compile(r"(?<!\w)(?:\+91[ -]?)?([6-9](?:[ -]?\d){9})(?!\w)")
FIR = re.compile(r"\b(FIR|CD)[ -]+(?:No\.?\s*)?([0-9]+(?:-[A-Z])?)(?:\s*[/\-]\s*|\s+)(20\d{2})\b", re.I)
SECTION_LIST = r"\d+[A-Za-z]?(?:\([A-Za-z0-9]+\))*(?:\s*(?:,|and|&)\s*\d+[A-Za-z]?(?:\([A-Za-z0-9]+\))*)*"
SECTIONS = re.compile(rf"(?P<codes>{SECTION_LIST})\s*(?P<law>BNS|IPC|Arms Act)\b", re.I)
LAW_FIRST = re.compile(rf"\b(?P<law>BNS|IPC|Arms Act)\s+(?:(?:sections?|u/s)\s*)?(?P<codes>{SECTION_LIST})", re.I)
SECTION_CODE = re.compile(r"\d+[A-Za-z]?(?:\([A-Za-z0-9]+\))*")


def vehicles(text: str) -> list[str]:
    return list(dict.fromkeys("".join(match.groups()).upper() for match in PLATE.finditer(text)))


def phone(text: str) -> str:
    match = PHONE.search(text)
    return re.sub(r"\D", "", match[1]) if match else ""


def fir_number(text: str) -> str:
    match = FIR.search(text)
    if not match:
        return ""
    return f"{match[1].upper()}-{match[2].upper()}/{match[3]}"


def statutes(text: str) -> list[tuple[str, str]]:
    matches = [*SECTIONS.finditer(text), *LAW_FIRST.finditer(text)]
    return list(dict.fromkeys(
        ("Arms Act" if match["law"].lower() == "arms act" else match["law"].upper(), code.upper())
        for match in matches for code in SECTION_CODE.findall(match["codes"])
    ))
