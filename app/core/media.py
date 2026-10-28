from urllib.parse import urlparse

from fastapi import HTTPException

from app.core.config import settings


def validate_photo_url(value: str | None) -> None:
    if value is None:
        return
    parsed = urlparse(value)
    if parsed.query or parsed.fragment or ".." in parsed.path.split("/"):
        raise HTTPException(422, "Invalid uploaded image URL")
    if not parsed.path.startswith("/uploads/") or parsed.path.endswith("/"):
        raise HTTPException(422, "Images must be uploaded through the API")
    if parsed.netloc:
        public = urlparse(settings.API_PUBLIC_URL)
        if not public.netloc or parsed.netloc.lower() != public.netloc.lower() or parsed.scheme != public.scheme:
            raise HTTPException(422, "Image URL does not belong to this API")
    elif parsed.scheme or value.startswith("//"):
        raise HTTPException(422, "Invalid uploaded image URL")
