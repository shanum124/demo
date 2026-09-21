class SummarizationWorker:
    def __init__(self, anthropic_client, vector_memory, redis_client): self.client, self.vector, self.redis = anthropic_client, vector_memory, redis_client
    async def process_queue(self): return None
