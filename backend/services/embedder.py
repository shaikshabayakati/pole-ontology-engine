import logging
import re
from hashlib import blake2b
from pathlib import Path
from threading import Lock

import numpy as np

from config import LOCAL_EMBEDDING_MODEL

logger = logging.getLogger(__name__)
_lock = Lock()
_model = None
_mode = "loading"


def load() -> None:
    global _model, _mode
    with _lock:
        if _mode != "loading":
            return
        try:
            from sentence_transformers import SentenceTransformer

            local = Path(__file__).resolve().parents[2] / ".model-cache" / "all-MiniLM-L6-v2"
            model_path = str(local) if LOCAL_EMBEDDING_MODEL in {
                "all-MiniLM-L6-v2", "sentence-transformers/all-MiniLM-L6-v2",
            } and (local / "model.safetensors").is_file() else LOCAL_EMBEDDING_MODEL
            _model = SentenceTransformer(model_path, device="cpu")
            if _model.get_sentence_embedding_dimension() != 384:
                raise ValueError("The embedding model must produce 384 dimensions")
            _mode = LOCAL_EMBEDDING_MODEL
        except Exception as error:
            logger.warning("Local embedding model unavailable (%s). Using lexical vectors.", type(error).__name__)
            _model = None
            _mode = "lexical-fallback"


def mode() -> str:
    return _mode


def embed_many(texts: list[str]) -> list[list[float]]:
    if _model is not None:
        with _lock:
            return _model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()
    vectors = []
    for text in texts:
        vector = np.zeros(384)
        for word in re.findall(r"\w+", text.casefold()):
            digest = int.from_bytes(blake2b(word.encode(), digest_size=8).digest(), "little")
            vector[digest % 384] += 1 if digest & 512 else -1
        norm = np.linalg.norm(vector)
        vectors.append((vector / norm if norm else vector).tolist())
    return vectors


def passage_vectors(chunks, documents):
    from services.normalizer import vehicles

    texts = []
    for chunk in chunks:
        station = documents.get(chunk["doc_id"], {}).get("police_station", "")
        identifiers = " ".join(vehicles(chunk["text"]))
        texts.append(f"{chunk['text']}\n{identifiers}\n{chunk['fir_number']} {station}")
    return embed_many(texts)


PASSAGE_VERSION = 2


def embed_text(text: str) -> list[float]:
    return embed_many([text])[0]
