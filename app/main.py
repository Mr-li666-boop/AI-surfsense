from fastapi import FastAPI

from app.routers import router_all

app = FastAPI()

app.include_router(router_all)