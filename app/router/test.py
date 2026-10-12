from fastapi import APIRouter

router = APIRouter()

@router.get("/lifly")
async def get_lifly():
    print("hello")
    return {"hello": "world"}