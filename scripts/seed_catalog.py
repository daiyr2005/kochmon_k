"""Seed the Kyrgyzstan listing catalog used by the frontend form."""
from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Category, City, Country


with SessionLocal() as db:
    country = db.scalar(select(Country).where(Country.code == "KG"))
    if not country:
        country = Country(name="Кыргызстан", code="KG")
        db.add(country)
        db.flush()

    for city_name in ("Бишкек", "Ош", "Чолпон-Ата", "Каракол", "Нарын", "Джалал-Абад", "Талас", "Баткен"):
        exists = db.scalar(
            select(City).where(City.name == city_name, City.country_id == country.id)
        )
        if not exists:
            db.add(City(name=city_name, country_id=country.id))

    for category_name in ("Квартира", "Дом", "Участок", "Отель", "Гостевой дом"):
        exists = db.scalar(
            select(Category).where(Category.name == category_name, Category.parent_id.is_(None))
        )
        if not exists:
            db.add(Category(name=category_name))

    db.commit()

print("Kyrgyzstan listing catalog ready")
