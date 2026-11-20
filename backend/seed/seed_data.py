import pymupdf

from services.ingestion_pipeline import ingest

RECORDS = (
    ("fir-104-2025", "FIR", """FIR-104/2025 | SYNTHETIC TRAINING RECORD
Police Station: Hindupur I Town PS
Crime: Highway robbery
Location: Gollapalli Cross, NH-44
Time: 21:15–21:30
Offence: 309(4) BNS
Complainant: K. Narayana
Suspect: Suri
The complainant reported a loss of INR 140,000. A witness heard one masked rider called Suri.
The witness stated that Suri rode the black Bajaj Pulsar AP 02 AB 1234 at Gollapalli Cross, NH-44."""),
    ("cd-104-b-2025", "Case Diary", """CD-104-B/2025 | SYNTHETIC TRAINING RECORD
Parent FIR: FIR-104/2025
Police Station: Hindupur I Town PS
Suspect: Suresh @ Suri; s/o Venkatappa; mobile: 9848011223
Associate: Ramesh @ Koti
Organisation: NH-44 Night Riders Gang
The investigating officer recorded Suresh @ Suri as an associate of Ramesh @ Koti.
The diary alleges that Suresh @ Suri and Ramesh @ Koti are members of NH-44 Night Riders Gang."""),
    ("fir-219-2025", "FIR", """FIR-219/2025 | SYNTHETIC TRAINING RECORD
Police Station: Penukonda PS
Crime: Warehouse burglary
Location: Penukonda electronics warehouse
Offence: 305, 331(4) BNS
Evidence: Iron bolt-cutter seized under memo SM-88/25
Suspect: Suresh @ Suri; s/o Venkatappa; mobile: 9848011223
Suspect: Md. Shake; s/o Nooruddin; mobile: 9440199887
The CCTV report alleges that Suresh @ Suri and Md. Shake rode AP-02-AB-1234 at Penukonda electronics warehouse."""),
    ("fir-042-2026", "FIR", """FIR-042/2026 | SYNTHETIC TRAINING RECORD
Police Station: Dharmavaram Town PS
Crime: Gold chain snatching
Location: Dharmavaram market road
Offence: 304(2) BNS
Suspect: Ramesh @ Koti
Suspect: Mohammed Shaik @ Shaiku; s/o Nooruddeen
A witness stated that Ramesh @ Koti and Mohammed Shaik @ Shaiku rode a white Apache RTR AP 39 KT 7788."""),
)

SAMPLE = (
    """FIR-517/2026 | SYNTHETIC TRAINING RECORD
Police Station: Penukonda PS
Document type: First Information Report
Crime: Theft of equipment
Location: NH-44 service road, Penukonda
Offence: 303(2) BNS
Complainant: Meera Rao
Suspect: Suresh @ Suri; s/o Venkatappa
The complainant reported that a generator was missing from a locked storage shed.
A witness stated that Suresh @ Suri rode AP 02 AB 1234 near the shed.
This synthetic document is for testing only.""",
    """FIR-517/2026 | EVIDENCE AND FOLLOW-UP
Evidence: Camera footage collected under seizure memo SM-517/26
Witness: N. Arun
The witness submitted a camera recording showing AP 02 AB 1234 near the shed.
Related Case: FIR-219/2025
The case officer recorded FIR-219/2025 as a related case for review.
This synthetic document is for testing only.""",
)


def seed(store):
    if not store.documents and not store.nodes:
        for name, kind, text in RECORDS:
            ingest(store, name + ".txt", text.encode(), document_type=kind, demo=True)


def sample_pdf():
    with pymupdf.open() as pdf:
        for index, text in enumerate(SAMPLE, 1):
            page = pdf.new_page(width=595, height=842)
            page.draw_rect(pymupdf.Rect(38, 39, 557, 111), color=(0.15, 0.24, 0.34), fill=(0.92, 0.95, 0.98))
            heading, content = text.split("\n", 1)
            page.insert_text((52, 70), heading, fontsize=14, fontname="hebo")
            page.insert_text((52, 92), "POLE+O | Demonstration record", fontsize=10, color=(0.3, 0.4, 0.48))
            page.insert_textbox(pymupdf.Rect(52, 139, 544, 738), content, fontsize=10.5, lineheight=1.65)
            page.insert_text((52, 790), f"Page {index} of {len(SAMPLE)}", fontsize=9)
        return pdf.tobytes(garbage=4, deflate=True, no_new_id=True)
