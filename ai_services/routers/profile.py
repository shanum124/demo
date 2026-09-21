from fastapi import APIRouter
router = APIRouter()
def configure(bridge):
    @router.get("/profile/{user_id}")
    async def profile(user_id: str): return await bridge.state_get_profile(user_id)
    @router.get("/telemetry/{user_id}")
    async def telemetry(user_id: str): return {"events": bridge.redis.lrange(f"telemetry:{user_id}", 0, -1) or []}
    return router
