"""Usage: python -m scripts.create_admin admin@example.com 'StrongPassword'"""
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.database import Base, SessionLocal, engine
from app.db.models import Role, User

email, password = sys.argv[1].lower(), sys.argv[2]
Base.metadata.create_all(engine)
with SessionLocal() as db:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        user.role = Role.admin
    else:
        db.add(User(email=email, password_hash=hash_password(password), role=Role.admin, email_verified=True))
    db.commit()
print("admin ready:", email)
