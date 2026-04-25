from fastapi import APIRouter

from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.documents import router as documents_router
from app.api.routes.evals import router as evals_router
from app.api.routes.feedback import router as feedback_router
from app.api.routes.health import router as health_router
from app.api.routes.knowledge_spaces import router as knowledge_spaces_router
from app.api.routes.queries import router as queries_router, trace_router
from app.api.routes.sources import router as sources_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(knowledge_spaces_router)
api_router.include_router(sources_router)
api_router.include_router(documents_router)
api_router.include_router(queries_router)
api_router.include_router(trace_router)
api_router.include_router(feedback_router)
api_router.include_router(evals_router)
api_router.include_router(dashboard_router)

