from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.database import get_db
from app.db.models import Category, City, Country
from app.db.schemas import (
    CategoryIn, CategoryNode, CategoryOut, CategoryPatch, CityIn, CityOut, CityPatch,
    CountryIn, CountryOut, CountryPatch,
)

countries = APIRouter()
cities = APIRouter()
categories = APIRouter()


def _get_or_404(db: Session, model, obj_id: int):
    obj = db.get(model, obj_id)
    if not obj:
        raise HTTPException(404, f"{model.__name__} not found")
    return obj


def _commit(db: Session, detail: str):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail)


def _create(db, model, data, detail):
    obj = model(**data.model_dump())
    db.add(obj)
    _commit(db, detail)
    return obj


def _patch(db, obj, data, detail):
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    _commit(db, detail)
    return obj


def _delete(db, obj):
    db.delete(obj)
    _commit(db, "Object is referenced by other records")
    return Response(status_code=204)


# ---- countries ----
@countries.get("/", response_model=list[CountryOut])
def list_countries(db: Session = Depends(get_db)):
    return db.scalars(select(Country).order_by(Country.name)).all()


@countries.get("/{country_id}", response_model=CountryOut)
def get_country(country_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, Country, country_id)


@countries.post("/", response_model=CountryOut, status_code=201, dependencies=[Depends(require_admin)])
def create_country(data: CountryIn, db: Session = Depends(get_db)):
    return _create(db, Country, data, "Country name or code already exists")


@countries.patch("/{country_id}", response_model=CountryOut, dependencies=[Depends(require_admin)])
def patch_country(country_id: int, data: CountryPatch, db: Session = Depends(get_db)):
    return _patch(db, _get_or_404(db, Country, country_id), data, "Country name or code already exists")


@countries.delete("/{country_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_country(country_id: int, db: Session = Depends(get_db)):
    return _delete(db, _get_or_404(db, Country, country_id))


# ---- cities ----
@cities.get("/", response_model=list[CityOut])
def list_cities(country_id: int | None = None, db: Session = Depends(get_db)):
    q = select(City).order_by(City.name)
    if country_id:
        q = q.where(City.country_id == country_id)
    return db.scalars(q).all()


@cities.get("/{city_id}", response_model=CityOut)
def get_city(city_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, City, city_id)


@cities.post("/", response_model=CityOut, status_code=201, dependencies=[Depends(require_admin)])
def create_city(data: CityIn, db: Session = Depends(get_db)):
    _get_or_404(db, Country, data.country_id)
    return _create(db, City, data, "City already exists in this country")


@cities.patch("/{city_id}", response_model=CityOut, dependencies=[Depends(require_admin)])
def patch_city(city_id: int, data: CityPatch, db: Session = Depends(get_db)):
    if data.country_id is not None:
        _get_or_404(db, Country, data.country_id)
    return _patch(db, _get_or_404(db, City, city_id), data, "City already exists in this country")


@cities.delete("/{city_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_city(city_id: int, db: Session = Depends(get_db)):
    return _delete(db, _get_or_404(db, City, city_id))


# ---- categories ----
@categories.get("/", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.scalars(select(Category).order_by(Category.name)).all()


@categories.get("/tree", response_model=list[CategoryNode])
def category_tree(db: Session = Depends(get_db)):
    rows = db.scalars(select(Category).order_by(Category.name)).all()
    nodes = {c.id: CategoryNode(id=c.id, name=c.name, children=[]) for c in rows}
    roots: list[CategoryNode] = []
    for c in rows:
        (nodes[c.parent_id].children if c.parent_id in nodes else roots).append(nodes[c.id])
    return roots


@categories.get("/{category_id}", response_model=CategoryOut)
def get_category(category_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, Category, category_id)


@categories.post("/", response_model=CategoryOut, status_code=201, dependencies=[Depends(require_admin)])
def create_category(data: CategoryIn, db: Session = Depends(get_db)):
    if data.parent_id is not None:
        _get_or_404(db, Category, data.parent_id)
    return _create(db, Category, data, "Category conflict")


@categories.patch("/{category_id}", response_model=CategoryOut, dependencies=[Depends(require_admin)])
def patch_category(category_id: int, data: CategoryPatch, db: Session = Depends(get_db)):
    cat = _get_or_404(db, Category, category_id)
    if data.parent_id is not None:
        # forbid cycles: walk up from the new parent
        cur = db.get(Category, data.parent_id)
        if not cur:
            raise HTTPException(404, "Parent category not found")
        while cur:
            if cur.id == cat.id:
                raise HTTPException(422, "Category cannot be its own ancestor")
            cur = db.get(Category, cur.parent_id) if cur.parent_id else None
    return _patch(db, cat, data, "Category conflict")


@categories.delete("/{category_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_category(category_id: int, db: Session = Depends(get_db)):
    return _delete(db, _get_or_404(db, Category, category_id))
