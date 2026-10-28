from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.db.database import get_db
from app.db.models import NotificationPreference, RefreshToken, User
from app.db.schemas import NotificationPreferencesIn, NotificationPreferencesOut, PasswordChange, TokenPair, UserOut, UserUpdate

router = APIRouter()

_NOTIFICATION_DEFAULTS = {
    "new_listings_by_category": True,
    "new_objects_in_city": True,
    "saved_price_change": True,
    "inquiry_replies": False,
    "booking_updates": False,
    "booking_reminders": False,
}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(data: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    db.commit()
    return user


@router.patch("/me/password", response_model=TokenPair)
def change_password(data: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(data.new_password)
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked=True))
    refresh, jti, expires = create_refresh_token(user.id)
    db.add(RefreshToken(id=jti, user_id=user.id, expires_at=expires))
    db.commit()
    return TokenPair(access_token=create_access_token(user.id), refresh_token=refresh)


@router.get("/me/notifications", response_model=NotificationPreferencesOut)
def get_notification_preferences(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    preferences = db.get(NotificationPreference, user.id)
    return preferences or _NOTIFICATION_DEFAULTS


@router.patch("/me/notifications", response_model=NotificationPreferencesOut)
def update_notification_preferences(
    data: NotificationPreferencesIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    preferences = db.get(NotificationPreference, user.id)
    if not preferences:
        preferences = NotificationPreference(user_id=user.id, **_NOTIFICATION_DEFAULTS)
        db.add(preferences)
    for key, value in data.model_dump().items():
        setattr(preferences, key, value)
    db.commit()
    return preferences


@router.delete("/me", status_code=204)
def delete_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.is_active = False  # soft delete keeps listings/payments referentially intact
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked=True))
    db.commit()
    return Response(status_code=204)
