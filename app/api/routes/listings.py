from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, get_optional_user
from app.core.media import validate_photo_url
from app.db.database import get_db
from app.db.models import Category, City, Country, Listing, ListingStatus, Role, User
from app.db.schemas import ListingIn, ListingOut, ListingPatch, Page

router = APIRouter()


def _can_manage(user: User, listing: Listing) -> bool:
    return user.id == listing.owner_id or user.role in (Role.admin, Role.moderator)


def _load_owned(db: Session, listing_id: int, user: User) -> Listing:
    listing = db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    if not _can_manage(user, listing):
        raise HTTPException(403, "Not your listing")
    return listing


def _check_refs(db: Session, category_id: int | None, city_id: int | None):
    if category_id is not None and not db.get(Category, category_id):
        raise HTTPException(422, "Unknown category_id")
    if city_id is not None and not db.get(City, city_id):
        raise HTTPException(422, "Unknown city_id")


@router.get("/", response_model=Page)
def list_listings(
    q: str | None = None,
    category_id: int | None = None,
    city_id: int | None = None,
    kind: str | None = None,
    city: str | None = None,
    country: str | None = None,
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    mine: bool = False,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    cond = []
    if mine:
        if not user:
            raise HTTPException(401, "Not authenticated")
        cond.append(Listing.owner_id == user.id)
    else:
        cond.append(Listing.status == ListingStatus.active)
    if q:
        cond.append(Listing.title.ilike(f"%{q}%"))
    if category_id:
        cond.append(Listing.category_id == category_id)
    if kind:
        cond.append(Listing.kind == kind)
    if city_id:
        cond.append(Listing.city_id == city_id)
    if city:
        cond.append(Listing.city_id.in_(select(City.id).where(City.name.ilike(f"%{city}%"))))
    if country:
        cond.append(
            Listing.city_id.in_(
                select(City.id).join(Country, City.country_id == Country.id)
                .where(Country.name.ilike(f"%{country}%"))
            )
        )
    if min_price is not None:
        cond.append(Listing.price >= min_price)
    if max_price is not None:
        cond.append(Listing.price <= max_price)
    total = db.scalar(select(func.count()).select_from(Listing).where(*cond)) or 0
    items = db.scalars(
        select(Listing).options(joinedload(Listing.city), joinedload(Listing.category))
        .where(*cond).order_by(Listing.created_at.desc(), Listing.id.desc())
        .offset((page - 1) * size).limit(size)
    ).all()
    return Page(items=items, total=total, page=page, size=size)


@router.post("/", response_model=ListingOut, status_code=201)
def create_listing(data: ListingIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _check_refs(db, data.category_id, data.city_id)
    validate_photo_url(data.photo_url)
    listing = Listing(**data.model_dump(), owner_id=user.id)
    db.add(listing)
    db.commit()
    return listing


@router.get("/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: int, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    listing = db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    if listing.status != ListingStatus.active and not (user and _can_manage(user, listing)):
        raise HTTPException(404, "Listing not found")  # hide drafts instead of leaking existence
    return listing


@router.patch("/{listing_id}", response_model=ListingOut)
def patch_listing(listing_id: int, data: ListingPatch, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    listing = _load_owned(db, listing_id, user)
    changes = data.model_dump(exclude_unset=True)
    _check_refs(db, changes.get("category_id"), changes.get("city_id"))
    validate_photo_url(changes.get("photo_url"))
    if changes.get("category_id", listing.category_id) is None or changes.get("city_id", listing.city_id) is None:
        raise HTTPException(422, "category_id and city_id cannot be null")
    for k, v in changes.items():
        setattr(listing, k, v)
    db.commit()
    return listing


@router.delete("/{listing_id}", status_code=204)
def delete_listing(listing_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(_load_owned(db, listing_id, user))
    db.commit()
    return Response(status_code=204)


@router.post("/{listing_id}/publish", response_model=ListingOut)
def publish(listing_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    listing = _load_owned(db, listing_id, user)
    if listing.status == ListingStatus.active:
        raise HTTPException(409, "Listing is already active")
    listing.status = ListingStatus.active
    db.commit()
    return listing


@router.post("/{listing_id}/deactivate", response_model=ListingOut)
def deactivate(listing_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    listing = _load_owned(db, listing_id, user)
    if listing.status != ListingStatus.active:
        raise HTTPException(409, "Only active listings can be deactivated")
    listing.status = ListingStatus.inactive
    db.commit()
    return listing
