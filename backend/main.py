import logging
from contextlib import asynccontextmanager
from pathlib import PurePath
from threading import Lock
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

import config
from database.neo4j_db import StorageUnavailable, Store
from schemas.ontology import Decision, Query
from seed.seed_data import sample_pdf, seed
from services import embedder
from services.graphrag_engine import search
from services.ingestion_pipeline import combine_nodes, edge_for, ingest, timestamp

logger = logging.getLogger(__name__)
store = Store()
jobs = {}
jobs_lock = Lock()


def startup():
    embedder.load()
    store.connect()
    store.refresh_embeddings()
    if config.SEED_DEMO:
        seed(store)


@asynccontextmanager
async def lifespan(_app):
    await run_in_threadpool(startup)
    try:
        yield
    finally:
        store.close()


app = FastAPI(title="POLE+O Police Ontology Engine", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=config.FRONTEND_ORIGINS, allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(StorageUnavailable)
async def storage_error(_request, error):
    return JSONResponse(status_code=503, content={"detail": str(error)})


@app.get("/api/status")
def status():
    with store.lock:
        return {
            "storage": store.storage,
            "database": config.NEO4J_DATABASE if store.storage == "neo4j" else None,
            "reason": store.reason,
            "embedding_model": embedder.mode(),
            "llm_configured": bool(config.OPENROUTER_API_KEY),
            "total_nodes": len(store.nodes),
            "total_documents": len(store.documents),
            "cross_case_links": sum(
                len({source["fir_number"] for source in node["sources"]}) > 1
                for node in store.nodes.values() if node["type"] in {"Vehicle", "Person"}
            ),
            "pending_reviews": sum(review["status"] == "PENDING" for review in store.reviews.values()),
        }


@app.get("/api/graph")
def graph():
    return store.graph()


@app.get("/api/graph/shortest-path")
def shortest_path(source_id: str, target_id: str):
    result = store.shortest_path(source_id, target_id)
    if result is None:
        raise HTTPException(404, "No connection found within six relationships.")
    return result


@app.get("/api/documents/sample.pdf")
def download_sample():
    return Response(sample_pdf(), media_type="application/pdf", headers={
        "Content-Disposition": 'attachment; filename="sample-fir-517-2026.pdf"',
    })


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: str):
    with store.lock:
        if doc_id not in store.documents:
            raise HTTPException(404, "Document not found.")
        return store.documents[doc_id]


def process_upload(job_id, file_name, data, police_station, document_type):
    def progress(stage):
        with jobs_lock:
            jobs[job_id]["stage"] = stage

    try:
        summary = ingest(store, file_name, data, police_station, document_type, progress=progress)
        with jobs_lock:
            jobs[job_id].update(status="complete", result=summary)
    except (ValueError, StorageUnavailable) as error:
        with jobs_lock:
            jobs[job_id].update(status="failed", error=str(error))
    except Exception:
        logger.exception("Document ingestion failed")
        with jobs_lock:
            jobs[job_id].update(status="failed", error="Document ingestion failed. Check the backend log.")


@app.post("/api/documents/upload")
async def upload(
    background: BackgroundTasks, file: UploadFile = File(...), police_station: str = Form("", max_length=160),
    document_type: str = Form("FIR", max_length=60), queued: bool = False,
):
    name = PurePath((file.filename or "").replace(chr(92), "/")).name
    if PurePath(name).suffix.lower() not in {".pdf", ".txt"}:
        raise HTTPException(415, "Choose a PDF or TXT file.")
    data = await file.read(config.MAX_UPLOAD_BYTES + 1)
    await file.close()
    if not data or len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Choose a non-empty file up to {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    if not queued:
        try:
            return await run_in_threadpool(ingest, store, name, data, police_station, document_type)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
    job_id = str(uuid4())
    with jobs_lock:
        if len(jobs) >= 100:
            for key in list(jobs):
                if jobs[key]["status"] != "running":
                    del jobs[key]
                if len(jobs) < 100:
                    break
        if len(jobs) >= 100:
            raise HTTPException(429, "Too many uploads are running.")
        jobs[job_id] = {"job_id": job_id, "status": "running", "stage": "parse"}
    background.add_task(process_upload, job_id, name, data, police_station, document_type)
    return {"job_id": job_id}


@app.get("/api/uploads/{job_id}")
def upload_progress(job_id: str):
    with jobs_lock:
        if job_id not in jobs:
            raise HTTPException(404, "Upload job not found.")
        return dict(jobs[job_id])


@app.post("/api/query")
def query(payload: Query):
    question = payload.question.strip()
    if not question:
        raise HTTPException(422, "Enter a question.")
    return search(store, question, payload)


@app.get("/api/reviews")
def reviews():
    with store.lock:
        return sorted(store.reviews.values(), key=lambda item: item["created_at"], reverse=True)


@app.post("/api/reviews/{review_id}")
def decide(review_id: str, payload: Decision):
    with store.lock:
        original = store.reviews.get(review_id)
        if original is None:
            raise HTTPException(404, "Review not found.")
        new_status = "APPROVED" if payload.decision == "approve" else "REJECTED"
        if original["status"] == new_status:
            return original
        if original["status"] != "PENDING":
            raise HTTPException(409, "This review already has a decision.")
        updated = {**original, "status": new_status}
        changes = [updated]
        entry = {
            "log_id": str(uuid4()), "action_type": f"REVIEW_{new_status}",
            "query_text": "", "details": review_id, "timestamp": timestamp(),
        }
        if payload.decision == "reject":
            store.decide(changes, entry)
            return updated
        source = original["source_entity"]["id"]
        target_id = original["target_entity"]["id"]
        if source not in store.nodes or target_id not in store.nodes:
            raise HTTPException(409, "The entities changed. Refresh the review queue.")
        target = combine_nodes(store.nodes[target_id], store.nodes[source])
        edges = {}
        for edge in store.edges.values():
            if source not in (edge["source"], edge["target"]):
                continue
            left = target_id if edge["source"] == source else edge["source"]
            right = target_id if edge["target"] == source else edge["target"]
            if left != right:
                value = edge_for(left, right, edge["type"], edge["citation"], edge["confidence"])
                edges[value["id"]] = value
        for key, review in store.reviews.items():
            if key == review_id or review["status"] != "PENDING":
                continue
            if any(review[field]["id"] == source for field in ("source_entity", "target_entity")):
                changes.append({**review, "status": "REJECTED", "match_rationale": review["match_rationale"] + " · superseded by merge"})
        store.decide(changes, entry, source=source, target=target, edges=list(edges.values()))
        return updated
