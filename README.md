# POLE+O · Police Ontology Engine

Local investigation workspace for PDF and UTF-8 case records. It extracts entities and relationships, resolves potential duplicates, and lets officers inspect paths and open the source lines behind each citation.

## Run on Windows

Install Python and Node.js, then run these commands from the repository root to set up the backend.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend
equirements.txt
Copy-Item backend\.env.example backend\.env
```

Start the backend and frontend in separate PowerShell windows, each beginning at the repository root.

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open [http://localhost:5173](http://localhost:5173). Interactive API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs). The backend uses the bundled all-MiniLM-L6-v2 cache or downloads the model on first launch. Set the SEED_DEMO environment variable to true to load four fictional records and a candidate identity review on an empty store. Use **Sample PDF** to download a two-page upload example, or use the fictional records in the sample-firs folder.

## Configuration

Add your own OpenRouter API key to the local environment file if you want model-assisted extraction and answers.

The local configuration is in `backend/.env`, which Git ignores. Use `backend/.env.example` to set up a fresh copy. Set `SEED_DEMO=false` before using a clean production database. Set `OPENROUTER_ENABLED=false` to keep extraction and answer synthesis local. With OpenRouter enabled, the service sends uploaded text for extraction and sends questions with retrieved excerpts for answer synthesis. Use only records approved for that processing. The application uses free model fallbacks, including the [OpenRouter free router](https://openrouter.ai/openrouter/free).

The default storage backend is a local SQLite database at `backend/data/pole.sqlite3`. It saves document text and page references, embeddings, the graph, reviews and query logs across backend restarts. Set `LOCAL_DB_PATH` to choose a different database file. For Neo4j, set `STORAGE_BACKEND=neo4j` and provide a reachable connection. Local and Neo4j records are stored separately. Run one backend process per database. Files with scanned pages need OCR before upload. Case assertions remain attributed to their sources.

Search combines local MiniLM passage vectors, BM25 term matching, normalized registrations and FIR identifiers, and graph neighborhoods. Lexical and dense ranks are fused before selecting up to five passages. Each passage retains its original page, lines, and verbatim text. At startup the backend refreshes older chunk embeddings in batches when the local model is available.

Person lookups rank indexed names and aliases using the supplied name, initials, and conversation details such as a station, FIR, vehicle, or incident. Ambiguous matches appear in chat with a similarity score, record references, and a confirmation action. A sufficiently separated exact match opens directly. Confirmed-person answers use source mentions and directly connected relationships. The similarity score is a ranking heuristic. “New chat” clears the conversation context.

Run the synthetic retrieval and disambiguation regression suite from the backend directory with `..\.venv\Scripts\python.exe -m unittest discover -s tests -v`.

The API binds to loopback by default and is intended for a single local operator. A shared deployment needs authentication, access control, and operational review before processing live records.
