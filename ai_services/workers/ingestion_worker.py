class IngestionWorker:
    STATES = ["UPLOADED", "PARSING", "NODE_MAPPING", "PYQ_TAGGING", "NOTES_CHUNKING", "CROSS_REFERENCE_READY", "STRATEGY_DRAFT_GENERATED", "READY"]
    def __init__(self, bridge): self.bridge = bridge
    async def run(self, user_id: str, uploaded_files: dict) -> None: return None
