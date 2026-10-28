"""Add listing fields introduced after the initial schema."""
from sqlalchemy import inspect, text

from app.db.database import Base, engine
from app.db import models  # noqa: F401


Base.metadata.create_all(engine)

with engine.begin() as connection:
    columns = {column["name"] for column in inspect(connection).get_columns("listings")}
    if "kind" not in columns:
        connection.execute(
            text("ALTER TABLE listings ADD COLUMN kind VARCHAR(32) NOT NULL DEFAULT 'Аренда'")
        )
    if "contact_phone" not in columns:
        connection.execute(text("ALTER TABLE listings ADD COLUMN contact_phone VARCHAR(32)"))
    if "photo_url" not in columns:
        connection.execute(text("ALTER TABLE listings ADD COLUMN photo_url VARCHAR(500)"))
    channel_link_columns = {column["name"] for column in inspect(connection).get_columns("channel_links")}
    if "attempts" not in channel_link_columns:
        connection.execute(text("ALTER TABLE channel_links ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0"))
    campaign_columns = {column["name"] for column in inspect(connection).get_columns("campaigns")}
    if "photo_url" not in campaign_columns:
        connection.execute(text("ALTER TABLE campaigns ADD COLUMN photo_url VARCHAR(500)"))

print("listing schema ready")
