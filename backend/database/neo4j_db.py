import json
import logging
from collections import deque
from threading import RLock

import numpy as np
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

import config
from database.local_db import LocalDatabase
from schemas.ontology import RELATIONSHIPS

logger = logging.getLogger(__name__)
UNAVAILABLE = (ServiceUnavailable, SessionExpired, TransientError)
VECTOR_CYPHER = (
    "CALL db.index.vector.queryNodes('chunk_vector_index', $limit, $embedding) "
    "YIELD node, score WHERE node.embedding_model = $model AND node.payload IS NOT NULL RETURN node.payload AS payload, score ORDER BY score DESC"
)
PATH_CYPHER = (
    "MATCH (a:OntologyEntity {id:$source}), (b:OntologyEntity {id:$target}) "
    "MATCH p=shortestPath((a)-[*..6]-(b)) "
    "WHERE all(r IN relationships(p) WHERE r.source_doc_id IS NOT NULL) "
    "RETURN [n IN nodes(p) | n.id] AS node_ids, "
    "[r IN relationships(p) | r.id] AS edge_ids"
)


def pack(value):
    return json.dumps(value, ensure_ascii=False)


def ontology_paths(graph, roots, depth=2, cap=80):
    adjacency = {}
    for edge in graph["edges"]:
        adjacency.setdefault(edge["source"], []).append((edge["target"], edge))
        adjacency.setdefault(edge["target"], []).append((edge["source"], edge))
    seen = set(roots)
    paths = {}
    queue = deque((root, 0) for root in roots)
    while queue and len(paths) < cap:
        node, distance = queue.popleft()
        if distance >= depth:
            continue
        for neighbor, edge in adjacency.get(node, []):
            paths[edge["id"]] = edge
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, distance + 1))
            if len(paths) >= cap:
                break
    return {
        "nodes": [node for node in graph["nodes"] if node["id"] in seen],
        "edges": list(paths.values()),
    }


class StorageUnavailable(RuntimeError):
    pass


class Store:
    def __init__(self):
        self.lock = RLock()
        self.driver = None
        self.local = None
        self.cloud_required = False
        self.storage = "memory"
        self.reason = "Neo4j is not configured"
        self.nodes = {}
        self.edges = {}
        self.documents = {}
        self.chunks = {}
        self.reviews = {}
        self.audit = []

    def connect(self):
        if config.STORAGE_BACKEND == "local":
            local = LocalDatabase(config.LOCAL_DB_PATH)
            records = local.load()
            self.nodes = records["nodes"]
            self.edges = records["edges"]
            self.documents = records["documents"]
            self.chunks = records["chunks"]
            self.reviews = records["reviews"]
            self.audit = list(records["audit"].values())
            self.local = local
            self.storage, self.reason = "sqlite", ""
            return
        if config.STORAGE_BACKEND != "neo4j":
            raise ValueError("STORAGE_BACKEND must be local or neo4j.")
        if not config.NEO4J_URI:
            raise ValueError("NEO4J_URI is required for Neo4j storage.")
        self.cloud_required = True
        try:
            self.driver = GraphDatabase.driver(
                config.NEO4J_URI, auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD),
                connection_timeout=4, connection_acquisition_timeout=7, max_transaction_retry_time=2,
            )
            self.driver.verify_connectivity()
            for label, key in (
                ("OntologyEntity", "id"), ("Document", "doc_id"), ("DocumentChunk", "chunk_id"),
                ("HITLReview", "review_id"), ("AuditLog", "log_id"),
            ):
                self.run(f"CREATE CONSTRAINT pole_{label.lower()} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{key} IS UNIQUE")
            self.run(
                "CREATE VECTOR INDEX chunk_vector_index IF NOT EXISTS FOR (c:DocumentChunk) ON (c.embedding) "
                "OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}}"
            )
            for label, key, target in (
                ("OntologyEntity", "id", self.nodes), ("Document", "doc_id", self.documents),
                ("DocumentChunk", "chunk_id", self.chunks), ("HITLReview", "review_id", self.reviews),
            ):
                vectors = ", n.embedding AS embedding" if label == "DocumentChunk" else ""
                for row in self.run(f"MATCH (n:{label}) WHERE n.payload IS NOT NULL RETURN n.payload AS payload{vectors}", read=True):
                    data = json.loads(row["payload"])
                    if vectors:
                        data["embedding"] = row["embedding"]
                    target[data[key]] = data
            for row in self.run("MATCH (:OntologyEntity)-[r]->(:OntologyEntity) WHERE r.payload IS NOT NULL RETURN r.payload AS payload", read=True):
                data = json.loads(row["payload"])
                self.edges[data["id"]] = data
            self.storage = "neo4j"
            self.reason = ""
        except Exception as error:
            self.close()
            raise StorageUnavailable("Could not open the configured Neo4j database.") from error

    def offline(self, reason):
        logger.warning("%s. Writes require a database connection.", reason)
        self.storage, self.reason = "unavailable", reason
        self.close()

    def close(self):
        if self.driver:
            self.driver.close()
            self.driver = None

    def run(self, query, read=False, **params):
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            execute = session.execute_read if read else session.execute_write
            return execute(lambda tx: tx.run(query, **params).data())

    def refresh_embeddings(self):
        from services import embedder

        if embedder.mode() == "lexical-fallback":
            return
        pending = [c for c in self.chunks.values() if c.get("passage_version") != embedder.PASSAGE_VERSION
                   or c.get("embedding_model") != embedder.mode()]
        for start in range(0, len(pending), 32):
            batch = pending[start:start + 32]
            vectors = embedder.passage_vectors(batch, self.documents)
            rows = []
            for chunk, vector in zip(batch, vectors, strict=True):
                metadata = {k: v for k, v in chunk.items() if k != "embedding"}
                metadata.update(embedding_model=embedder.mode(), passage_version=embedder.PASSAGE_VERSION)
                rows.append({"id": chunk["chunk_id"], "vector": vector, "payload": pack(metadata)})
            self.transaction(lambda tx: tx.run(
                "UNWIND $rows AS row MATCH (c:DocumentChunk {chunk_id:row.id}) "
                "SET c.embedding=row.vector, c.payload=row.payload, c.embedding_model=$model, c.passage_version=$version",
                rows=rows, model=embedder.mode(), version=embedder.PASSAGE_VERSION).consume())
            updated = [
                dict(chunk, embedding=vector, embedding_model=embedder.mode(), passage_version=embedder.PASSAGE_VERSION)
                for chunk, vector in zip(batch, vectors, strict=True)
            ]
            if self.local:
                self.local.write({"chunks": updated})
            self.chunks.update((chunk["chunk_id"], chunk) for chunk in updated)

    def graph(self):
        with self.lock:
            return {"nodes": list(self.nodes.values()), "edges": list(self.edges.values())}

    @staticmethod
    def document_data(document, chunks):
        def rows(tx):
            record = {key: value for key, value in document.items() if key != "pages"}
            tx.run(
                "MERGE (d:Document {doc_id:$key}) SET d += $props, d.payload=$payload",
                key=document["doc_id"], props=record, payload=pack(document),
            ).consume()
            batch = []
            for chunk in chunks:
                data = {key: value for key, value in chunk.items() if key != "embedding"}
                batch.append({"chunk": chunk, "payload": pack(data)})
            tx.run(
                "UNWIND $batch AS row MATCH (d:Document {doc_id:$doc}) "
                "MERGE (c:DocumentChunk {chunk_id:row.chunk.chunk_id}) SET c += row.chunk, "
                "c.source_fir=row.chunk.fir_number, c.payload=row.payload MERGE (c)-[:PART_OF]->(d)",
                batch=batch, doc=document["doc_id"],
            ).consume()
        return rows

    @staticmethod
    def write_nodes(tx, nodes):
        groups = {}
        for node in nodes:
            groups.setdefault(node["type"], []).append({
                "id": node["id"], "name": node["name"], "props": node["properties"], "payload": pack(node),
            })
        for label, rows in groups.items():
            tx.run(
                f"UNWIND $rows AS row MERGE (n:OntologyEntity {{id:row.id}}) SET n:{label}, "
                "n += row.props, n.name=row.name, n.payload=row.payload",
                rows=rows,
            ).consume()

    @staticmethod
    def write_edges(tx, edges):
        groups = {}
        for edge in edges:
            groups.setdefault(edge["type"], []).append({
                "id": edge["id"], "source": edge["source"], "target": edge["target"],
                "citation": edge["citation"], "confidence": edge["confidence"], "payload": pack(edge),
            })
        for kind, rows in groups.items():
            if kind not in RELATIONSHIPS:
                raise ValueError("Unsupported relationship type")
            tx.run(
                "UNWIND $rows AS row MATCH (a:OntologyEntity {id:row.source}), (b:OntologyEntity {id:row.target}) "
                f"MERGE (a)-[r:{kind} {{id:row.id}}]->(b) SET r += row.citation, "
                "r.source_doc_id=row.citation.doc_id, r.source_fir=row.citation.fir_number, "
                "r.confidence=row.confidence, r.payload=row.payload", rows=rows,
            ).consume()

    @staticmethod
    def write_reviews(tx, reviews):
        rows = []
        for review in reviews:
            props = {key: value for key, value in review.items() if key not in {"source_entity", "target_entity"}}
            props["source_entity_json"] = pack(review["source_entity"])
            props["target_entity_json"] = pack(review["target_entity"])
            props["target_entity_id"] = review["target_entity"]["id"]
            rows.append({"props": props, "payload": pack(review)})
        tx.run(
            "UNWIND $rows AS row MERGE (h:HITLReview {review_id:row.props.review_id}) "
            "SET h += row.props, h.payload=row.payload", rows=rows,
        ).consume()

    def transaction(self, work):
        if self.cloud_required and self.driver is None:
            raise StorageUnavailable("Neo4j is unavailable. Restart the backend once the connection is restored.")
        if self.driver:
            try:
                with self.driver.session(database=config.NEO4J_DATABASE) as session:
                    session.execute_write(work)
            except UNAVAILABLE as error:
                self.offline(f"Neo4j connection interrupted ({type(error).__name__})")
                raise StorageUnavailable("Neo4j disconnected before the write could be confirmed.") from error

    def commit_document(self, doc, chunks, nodes, edges, reviews, mentions):
        def work(tx):
            self.document_data(doc, chunks)(tx)
            self.write_nodes(tx, nodes)
            self.write_edges(tx, edges)
            self.write_reviews(tx, reviews)
            tx.run(
                "UNWIND $mentions AS row MATCH (c:DocumentChunk {chunk_id:row.chunk_id}), "
                "(n:OntologyEntity {id:row.entity_id}) MERGE (c)-[:MENTIONS]->(n)", mentions=mentions,
            ).consume()

        self.transaction(work)
        if self.local:
            self.local.write({
                "documents": [doc], "chunks": chunks, "nodes": nodes, "edges": edges, "reviews": reviews,
            })
        self.documents[doc["doc_id"]] = doc
        self.chunks.update((chunk["chunk_id"], chunk) for chunk in chunks)
        self.nodes.update((node["id"], node) for node in nodes)
        self.edges.update((edge["id"], edge) for edge in edges)
        self.reviews.update((review["review_id"], review) for review in reviews)

    def decide(self, reviews, audit, source=None, target=None, edges=()):
        def work(tx):
            if source is not None:
                self.write_nodes(tx, [target])
                tx.run(
                    "MATCH (source:OntologyEntity {id:$source}), (target:OntologyEntity {id:$target}) "
                    "OPTIONAL MATCH (c:DocumentChunk)-[:MENTIONS]->(source) "
                    "FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END | MERGE (c)-[:MENTIONS]->(target))",
                    source=source, target=target["id"],
                ).consume()
                tx.run("MATCH (n:OntologyEntity {id:$source}) DETACH DELETE n", source=source).consume()
                self.write_edges(tx, edges)
            self.write_reviews(tx, reviews)
            self.write_audit(tx, audit)

        removed_edges = [
            key for key, edge in self.edges.items() if source is not None and source in (edge["source"], edge["target"])
        ]
        self.transaction(work)
        if self.local:
            changes = {"reviews": reviews, "audit": [audit]}
            removals = []
            if source is not None:
                changes.update(nodes=[target], edges=edges)
                removals = [("nodes", source), *(("edges", key) for key in removed_edges)]
            self.local.write(changes, removals)
        if source is not None:
            del self.nodes[source]
            self.nodes[target["id"]] = target
            for key in removed_edges:
                del self.edges[key]
            self.edges.update((edge["id"], edge) for edge in edges)
        self.reviews.update((review["review_id"], review) for review in reviews)
        self.audit.append(audit)

    @staticmethod
    def write_audit(tx, entry):
        tx.run("MERGE (a:AuditLog {log_id:$id}) SET a += $props", id=entry["log_id"], props=entry).consume()

    def log(self, entry):
        with self.lock:
            self.transaction(lambda tx: self.write_audit(tx, entry))
            if self.local:
                self.local.write({"audit": [entry]})
            self.audit.append(entry)

    def vector_search(self, embedding, embedding_model, limit=5):
        with self.lock:
            if self.driver:
                try:
                    candidates = self.run(VECTOR_CYPHER, read=True, limit=limit * 4, embedding=embedding, model=embedding_model)
                    rows = [{"score": 2 * float(row["score"]) - 1, **json.loads(row["payload"])} for row in candidates]
                    if len(rows) >= min(limit, sum(chunk.get("embedding_model") == embedding_model for chunk in self.chunks.values())):
                        return rows[:limit]
                except UNAVAILABLE as error:
                    self.offline(f"Neo4j vector query interrupted ({type(error).__name__})")
                except Exception as error:
                    logger.info("Vector index unavailable (%s), using cosine search", type(error).__name__)
            query = np.asarray(embedding, dtype=float)
            query_norm = np.linalg.norm(query)
            rows = []
            for chunk in self.chunks.values():
                if chunk.get("embedding_model") != embedding_model:
                    continue
                vector = np.asarray(chunk["embedding"], dtype=float)
                divisor = np.linalg.norm(vector) * query_norm
                score = float(np.dot(query, vector) / divisor) if divisor else 0.0
                rows.append({"score": score, **{key: value for key, value in chunk.items() if key != "embedding"}})
            return sorted(rows, key=lambda row: -row["score"])[:limit]

    def shortest_path(self, source, target):
        with self.lock:
            if source not in self.nodes or target not in self.nodes:
                return None
            if source == target:
                return {"nodes": [self.nodes[source]], "edges": []}
            if self.driver:
                try:
                    records = self.run(PATH_CYPHER, read=True, source=source, target=target)
                    if records:
                        record = records[0]
                        return {
                            "nodes": [self.nodes[key] for key in record["node_ids"]],
                            "edges": [self.edges[key] for key in record["edge_ids"]],
                        }
                    return None
                except UNAVAILABLE as error:
                    self.offline(f"Neo4j path query interrupted ({type(error).__name__})")
            adjacency = {}
            for edge in self.edges.values():
                adjacency.setdefault(edge["source"], []).append((edge["target"], edge))
                adjacency.setdefault(edge["target"], []).append((edge["source"], edge))
            visited = {source}
            queue = deque([(source, [source], [])])
            while queue:
                current, nodes, edges = queue.popleft()
                if current == target:
                    return {"nodes": [self.nodes[key] for key in nodes], "edges": edges}
                if len(edges) == 6:
                    continue
                for neighbor, edge in adjacency.get(current, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, [*nodes, neighbor], [*edges, edge]))
            return None
