import os
import uuid
from pathlib import Path

# Avoid eager thread pools during API startup and test collection.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

from qdrant_client import QdrantClient, models

from ai_services.schemas.mcp_schemas import VectorSearchResult


class VectorStore:
    """Local Qdrant vector store backed by a semantic embedding model when available."""

    COLLECTION = "notes_chunks"
    VECTOR_SIZE = 384

    def __init__(self, path: Path | None = None, url: str | None = None, api_key: str | None = None, collection_name: str = COLLECTION, embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2", vector_size: int = 384, local_files_only: bool = True):
        self._items: dict[str, dict] = {}
        self.COLLECTION = collection_name
        self.embedding_model_name = embedding_model
        self.VECTOR_SIZE = vector_size
        self.local_files_only = local_files_only
        self.embedding_model = None
        self._embedding_load_attempted = False
        self._embedding_load_error: Exception | None = None
        self.client = QdrantClient(url=url, api_key=api_key) if url else QdrantClient(path=str(path))
        if not self.client.collection_exists(self.COLLECTION):
            self.client.create_collection(
                collection_name=self.COLLECTION,
                vectors_config=models.VectorParams(size=self.VECTOR_SIZE, distance=models.Distance.COSINE),
            )

    def _ensure_embedding_model(self):
        if self.embedding_model is not None:
            return
        if self._embedding_load_attempted:
            raise RuntimeError(
                f"Unable to load semantic embedding model {self.embedding_model_name!r}. "
                "Install or cache the configured model before indexing documents."
            ) from self._embedding_load_error
        self._embedding_load_attempted = True
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(self.embedding_model_name, local_files_only=self.local_files_only)
            dimension = model.get_embedding_dimension() if hasattr(model, "get_embedding_dimension") else model.get_sentence_embedding_dimension()
            if dimension != self.VECTOR_SIZE:
                raise ValueError(
                    f"Embedding model {self.embedding_model_name!r} returns {dimension} dimensions; "
                    f"collection {self.COLLECTION!r} requires {self.VECTOR_SIZE}."
                )
            self.embedding_model = model
        except Exception as exc:
            self._embedding_load_error = exc
            raise RuntimeError(
                f"Unable to load semantic embedding model {self.embedding_model_name!r}. "
                "Install or cache the configured model before indexing documents."
            ) from exc

    @staticmethod
    def _point_id(chunk_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"adaptive-engine:{chunk_id}"))

    def _embed(self, text: str) -> list[float]:
        if self.embedding_model is None:
            self._ensure_embedding_model()
        vector = self.embedding_model.encode(text, convert_to_tensor=False, normalize_embeddings=True)
        return [float(value) for value in vector]

    def rank_texts(self, query: str, candidates: list[str]) -> list[float]:
        """Return cosine similarity scores in the configured semantic embedding space."""
        if not candidates:
            return []
        query_vector = self._embed(query)
        candidate_vectors = [self._embed(candidate) for candidate in candidates]
        return [sum(left * right for left, right in zip(query_vector, candidate)) for candidate in candidate_vectors]

    async def search(self, query: str, node_ids: list[str] | None = None, top_k: int = 5, exam_id: str | None = None) -> list[VectorSearchResult]:
        filters = []
        if node_ids:
            filters.append(models.FieldCondition(key="node_id", match=models.MatchAny(any=node_ids)))
        if exam_id:
            filters.append(models.FieldCondition(key="exam_id", match=models.MatchValue(value=exam_id)))
        query_filter = models.Filter(must=filters) if filters else None
        results = self.client.query_points(
            collection_name=self.COLLECTION,
            query=self._embed(query),
            query_filter=query_filter,
            limit=min(top_k, 5),
            with_payload=True,
        ).points
        return [
            VectorSearchResult(
                chunk_id=p.payload.get("chunk_id", ""),
                score=float(p.score),
                snippet=p.payload.get("text", "")[:500],
                node_id=p.payload.get("node_id", ""),
                source_doc_id=p.payload.get("source_doc_id", ""),
                page=p.payload.get("page"),
                section=p.payload.get("section"),
            )
            for p in results
        ]

    async def ingest(self, chunks: list[dict]) -> None:
        self._items.update({chunk["chunk_id"]: chunk for chunk in chunks})
        self.client.upsert(
            collection_name=self.COLLECTION,
            points=[models.PointStruct(id=self._point_id(chunk["chunk_id"]), vector=self._embed(chunk["text"]), payload={"chunk_id": chunk["chunk_id"], "node_id": chunk["node_id"], "source_doc_id": chunk.get("source_doc_id", ""), "exam_id": chunk.get("exam_id", ""), "page": chunk.get("page"), "section": chunk.get("section"), "text": chunk["text"]}) for chunk in chunks],
        )
