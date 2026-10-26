"""FairDecide AI API.   Run:  .venv\\Scripts\\python -m uvicorn backend.main:app --port 8000"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import events, state
from .api_data import router as data_router
from .api_engine import router as engine_router
from .db import close
from .engine.recommender import Recommender


@asynccontextmanager
async def lifespan(app):
    events.bind_loop(asyncio.get_running_loop())
    state.rec = Recommender()             # loads data, model and SHAP explainer once (~2 s)
    yield
    close()


app = FastAPI(title="FairDecide AI", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(data_router)
app.include_router(engine_router)
