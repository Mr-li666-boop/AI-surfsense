from fastapi import FastAPI

from app.router import router_all

app = FastAPI()

app.include_router(router_all)