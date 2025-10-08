from fastapi import FastAPI
from . import health, start, export_pdf
# from . import health, start, artifacts, agents, hitl

def register_routes(app: FastAPI):
    app.include_router(health.router, )
    app.include_router(start.router)
    app.include_router(export_pdf.router)

