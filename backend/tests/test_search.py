import unittest
from unittest.mock import patch

from database.neo4j_db import Store
from schemas.ontology import Query
from services import embedder
from services.graphrag_engine import search
from services.hybrid import retrieve
from services.ingestion_pipeline import ingest


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        for number, name, station, plate in [
            (101, "Ravi Pal", "Hindupur", "AP 02 AB 1234"),
            (102, "Ravi Patel", "Penukonda", "AP 02 CD 4567"),
            (103, "Ravi Singh", "Dharmavaram", "AP 39 KT 7788"),
        ]:
            text = f"FIR-{number}/2025\nPolice Station: {station} PS\nCrime: {'Warehouse burglary' if number == 102 else 'Theft'}\nWitness: {name}\n{name} rode {plate}."
            ingest(self.store, f"{number}.txt", text.encode(), demo=True)
        self.addCleanup(patch.stopall)
        patch("services.graphrag_engine.call_llm_json", return_value={}).start()

    def ask(self, question, **kwargs):
        return search(self.store, question, Query(question=question, **kwargs))

    def test_initial_and_context_then_confirm(self):
        initial = self.ask("Find Ravi P")
        self.assertEqual(initial["resolution"], "clarify")
        self.assertEqual(len(initial["candidates"]), 3)
        self.assertFalse(initial["citations"])
        pending = initial["pending_question"]
        follow = self.ask("Hindupur", history=[pending], pending_question=pending)
        self.assertEqual(follow["resolution"], "confirm")
        self.assertEqual(follow["candidates"][0]["name"], "Ravi Pal")
        final = self.ask("yes", history=[pending, "Hindupur"], pending_question=pending)
        self.assertEqual(final["person_id"], follow["candidates"][0]["id"])
        self.assertEqual({s["fir_number"] for s in final["citations"]}, {"FIR-101/2025"})

    def test_first_name_prior_context_and_click(self):
        reply = self.ask("Ravi", history=["Search FIR-102/2025"])
        self.assertEqual(reply["candidates"][0]["name"], "Ravi Patel")
        selected = reply["candidates"][-1]
        final = self.ask("Confirm", pending_question="Ravi", selected_id=selected["id"])
        self.assertEqual(final["person_id"], selected["id"])

    def test_exact_and_unknown(self):
        reply = self.ask("Find Ravi Pal")
        self.assertEqual(reply["resolution"], "answer")
        self.assertEqual(reply["answer"], "Ravi Pal [1]")
        self.assertFalse(self.ask("Who is Abhinav Menon?")["citations"])

    def test_incident_context_and_surname_reply(self):
        contextual = self.ask("Find Ravi", history=["Show me the warehouse burglary"])
        self.assertEqual(contextual["candidates"][0]["name"], "Ravi Patel")
        reply = self.ask("Pal", history=["Find Ravi"], pending_question="Find Ravi")
        self.assertEqual(reply["resolution"], "confirm")
        self.assertEqual(reply["candidates"][0]["name"], "Ravi Pal")
        self.assertEqual(self.ask("yes", history=["Find Ravi", "Pal"], pending_question="Find Ravi")["person_id"],
                         reply["candidates"][0]["id"])

    def test_alias_and_shared_full_name(self):
        pal = next(n for n in self.store.nodes.values() if n["name"] == "Ravi Pal")
        pal["properties"]["aliases"] = ["Raju"]
        self.assertEqual(self.ask("Find Raju")["candidates"][0]["id"], pal["id"])
        other = next(n for n in self.store.nodes.values() if n["name"] == "Ravi Patel")
        other["name"] = "Ravi Pal"
        ambiguous = self.ask("Find Ravi Pal")
        self.assertEqual(ambiguous["resolution"], "clarify")
        self.assertFalse(ambiguous["citations"])
        referenced = self.ask("Ravi from that case", previous_cases=["FIR-102/2025"])
        self.assertEqual(referenced["candidates"][0]["id"], other["id"])

    def test_confirmed_person_answer_includes_narrative(self):
        text = ("FIR-900/2026\nPolice Station: Test PS\nComplainant: K. Narayana\n"
                "The complainant reported a loss of INR 140,000 after two masked men stopped him near NH-44.\n"
                "He gave a written statement to the officer. No injury was reported.")
        ingest(self.store, "narrative.txt", text.encode(), demo=True)
        person = next(n for n in self.store.nodes.values() if n["name"] == "K. Narayana")
        reply = self.ask("Confirm K. Narayana", pending_question="What did Narayana do?",
                         selected_id=person["id"], history=["What did Narayana do?"])
        self.assertIn("140,000", reply["answer"])
        self.assertIn("complainant", reply["answer"].lower())
        self.assertTrue(any("140,000" in c["verbatim_quote"] for c in reply["citations"]))
        with patch("services.graphrag_engine.call_llm_json", return_value={
            "claims": [{"text": "K. Narayana reported a robbery and gave a written statement.",
                        "source_ids": [2]}]
        }) as llm:
            reply = self.ask("Confirm K. Narayana", pending_question="What did Narayana do?",
                             selected_id=person["id"])
            self.assertIn("reported a robbery", reply["answer"])
            prompt = llm.call_args.args[1]
            self.assertIn("What did Narayana do?", prompt)
            self.assertIn("140,000", prompt)

    def test_dense_lexical_fusion(self):
        results = retrieve(self.store, "Case with AP02CD4567")
        self.assertEqual(results[0]["fir_number"], "FIR-102/2025")
        self.assertTrue(all(c["verbatim_quote"] == c["text"] for c in results))
