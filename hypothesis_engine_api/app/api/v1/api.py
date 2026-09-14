from fastapi import APIRouter

from app.api.v1.endpoints import (
    agents,
    channel_context,
    channels,
    evidence,
    health,
    hypotheses,
    hypothesis_context,
    insights,
    keys,
    relationships,
    timeline,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(hypotheses.router)
api_router.include_router(evidence.router)
api_router.include_router(timeline.router)
api_router.include_router(agents.router)
api_router.include_router(relationships.router)
api_router.include_router(insights.router)
api_router.include_router(keys.router)
api_router.include_router(channel_context.router)
api_router.include_router(hypothesis_context.router)
api_router.include_router(channels.router)
