from fastapi import FastAPI

from jobharbor.api.review import router as review_router

app = FastAPI()
app.include_router(review_router)


@app.get('/health')
def health() -> dict[str, bool]:
    return {'ok': True}
