from contextlib import asynccontextmanager

from fastapi import FastAPI
import gradio as gr
from gradio import mount_gradio_app

from app.api.v1.middleware import auth_middleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.llm.llms import init_general_agent
from app.services.assistant import init_assistant_service
from app.services.mcp_client import postgres_mcp_tools
from app.ui.gradio_app import create_ui

# main.py

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with postgres_mcp_tools() as tools:
        general_agent = init_general_agent(tools)
        init_assistant_service(general_agent)

        yield


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     await list_postgres_tools()
#     await init_general_agent()
#     init_assistant_service()
#     yield

def create_app() -> FastAPI:
    application = FastAPI(title=settings.PROJECT_NAME, debug=settings.DEBUG, lifespan=lifespan)
    application.middleware("http")(auth_middleware)
    application.include_router(api_router, prefix=settings.API_V1_PREFIX)
    return application


app = create_app()

demo = create_ui()

app = gr.mount_gradio_app(
    app,
    demo,
    path="/assistant"
)
