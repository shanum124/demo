from ai_services.stores.vector_store import VectorStore
class VectorMemory:
    def __init__(self, vector_store: VectorStore): self.store = vector_store
    async def search(self, query, node_ids=None, top_k=5): return await self.store.search(query, node_ids, min(top_k, 5))
    async def ingest_chunks(self, chunks): await self.store.ingest(chunks)
    async def store_session_digest(self, thread_id, node_ids, digest_text): await self.store.ingest([{"chunk_id": f"digest:{thread_id}", "node_id": node_ids[0] if node_ids else "", "text": digest_text}])
