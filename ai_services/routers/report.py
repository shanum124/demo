from fastapi import APIRouter
from pydantic import BaseModel
router = APIRouter()
def configure(markdown_store):
    @router.get("/report")
    async def report(doc_id: str = "strategy"): return {"doc_id": doc_id, "markdown": markdown_store.read(doc_id)}
    class Patch(BaseModel): section: str; patch: str
    @router.patch("/report")
    async def patch(body: Patch, doc_id: str = "strategy"):
        return {"version": markdown_store.write_patch(doc_id, body.section, body.patch)}
    return router
