from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.database import get_db
from app.db.models import Favorite, Listing, ListingStatus, User
from app.db.schemas import ListingOut

router = APIRouter()


@router.get("/", response_model=list[ListingOut])
def my_favorites(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(
        select(Listing).join(Favorite, Favorite.listing_id == Listing.id)
        .where(Favorite.user_id == user.id).order_by(Favorite.created_at.desc())
    ).all()


@router.post("/{listing_id}", status_code=201)
def add_favorite(listing_id: int, response: Response, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    listing = db.get(Listing, listing_id)
    if not listing or (listing.status != ListingStatus.active and listing.owner_id != user.id):
        raise HTTPException(404, "Listing not found")
    if db.get(Favorite, (user.id, listing_id)):
        response.status_code = 200  # idempotent: duplicate request is not an error
        return {"listing_id": listing_id, "favorite": True}
    db.add(Favorite(user_id=user.id, listing_id=listing_id))
    db.commit()
    return {"listing_id": listing_id, "favorite": True}


@router.delete("/{listing_id}", status_code=204)
def remove_favorite(listing_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    fav = db.get(Favorite, (user.id, listing_id))
    if not fav:
        raise HTTPException(404, "Not in favorites")
    db.delete(fav)
    db.commit()
    return Response(status_code=204)
