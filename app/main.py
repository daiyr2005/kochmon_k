from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, catalog, favorites, integrations, listings, users
from app.core.config import settings
from app.db.database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Dev convenience only. In production use Alembic migrations.
    if settings.AUTO_CREATE_TABLES or settings.DATABASE_URL.startswith("sqlite"):
        Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Kochmon API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = "/api"
app.include_router(auth.router, prefix=f"{api}/auth", tags=["auth"])
app.include_router(users.router, prefix=f"{api}/users", tags=["users"])
app.include_router(catalog.countries, prefix=f"{api}/countries", tags=["countries"])
app.include_router(catalog.cities, prefix=f"{api}/cities", tags=["cities"])
app.include_router(catalog.categories, prefix=f"{api}/categories", tags=["categories"])
app.include_router(listings.router, prefix=f"{api}/listings", tags=["listings"])
app.include_router(favorites.router, prefix=f"{api}/favorites", tags=["favorites"])
app.include_router(integrations.search, prefix=f"{api}/search", tags=["search"])
app.include_router(integrations.ai, prefix=f"{api}/ai", tags=["ai"])
app.include_router(integrations.channels, prefix=f"{api}/channels", tags=["channels"])
app.include_router(integrations.advertising, prefix=f"{api}/advertising", tags=["advertising"])
app.include_router(integrations.uploads, prefix=f"{api}/uploads", tags=["uploads"])
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.get("/api/health")
def health():
    return {"status": "ok"}
