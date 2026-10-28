import hashlib
import secrets
import smtplib
from datetime import timedelta
from email.message import EmailMessage
from urllib.parse import urlencode, quote

import jwt
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token, create_refresh_token, decode_token, hash_password, verify_password,
)
from app.db.database import get_db
from app.db.models import PasswordReset, RefreshToken, User, utcnow
from app.db.schemas import (
    LoginIn, PasswordResetConfirm, PasswordResetRequest, RefreshIn, RegisterIn, TokenPair, UserOut,
)

router = APIRouter()
oauth_state_cookie = "kochmon_google_oauth_state"


def _issue(db: Session, user: User) -> TokenPair:
    refresh, jti, exp = create_refresh_token(user.id)
    db.add(RefreshToken(id=jti, user_id=user.id, expires_at=exp))
    db.commit()
    return TokenPair(access_token=create_access_token(user.id), refresh_token=refresh)


@router.post("/register", response_model=UserOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    user = User(email=email, password_hash=hash_password(data.password), full_name=data.full_name)
    db.add(user)
    db.commit()
    return user


@router.post("/login", response_model=TokenPair)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash) or not user.is_active:
        raise HTTPException(401, "Invalid credentials")
    return _issue(db, user)


@router.post("/refresh", response_model=TokenPair)
def refresh(data: RefreshIn, db: Session = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token)
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid token type")
    row = db.get(RefreshToken, payload["jti"])
    if not row:
        raise HTTPException(401, "Unknown refresh token")
    if row.revoked:
        # reuse of a rotated token => assume theft, kill the whole session family
        db.execute(update(RefreshToken).where(RefreshToken.user_id == row.user_id).values(revoked=True))
        db.commit()
        raise HTTPException(401, "Refresh token reuse detected")
    user = db.get(User, row.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "User not found or inactive")
    row.revoked = True
    return _issue(db, user)


@router.post("/logout", status_code=204)
def logout(data: RefreshIn, db: Session = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token)
    except jwt.PyJWTError:
        return Response(status_code=204)  # idempotent
    row = db.get(RefreshToken, payload.get("jti", ""))
    if row:
        row.revoked = True
        db.commit()
    return Response(status_code=204)


@router.get("/google")
def google_login():
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(503, "Google OAuth is not configured")
    state = jwt.encode(
        {"state": secrets.token_urlsafe(24), "type": "google_oauth", "exp": utcnow() + timedelta(minutes=10)},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    response = RedirectResponse(
        "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        })
    )
    response.set_cookie(
        oauth_state_cookie, state, httponly=True, secure=settings.GOOGLE_REDIRECT_URI.startswith("https://"),
        samesite="lax", max_age=600,
    )
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    def fail(reason: str):
        response = RedirectResponse(f"{settings.FRONTEND_URL}/?{urlencode({'error': reason})}")
        response.delete_cookie(oauth_state_cookie)
        return response

    if error or not code or not state or not request.cookies.get(oauth_state_cookie):
        return fail("google_login_failed")
    try:
        claims = jwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return fail("google_login_failed")
    if claims.get("type") != "google_oauth" or not secrets.compare_digest(
        state, request.cookies[oauth_state_cookie]
    ):
        return fail("google_login_failed")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")
            if not access_token:
                return fail("google_login_failed")
            profile_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            profile_response.raise_for_status()
            profile = profile_response.json()
    except (httpx.RequestError, httpx.HTTPStatusError):
        return fail("google_login_failed")
    email = str(profile.get("email", "")).lower()
    if not email or not profile.get("verified_email"):
        return fail("google_login_failed")
    user = db.scalar(select(User).where(User.email == email))
    if user and not user.is_active:
        return fail("account_disabled")
    if not user:
        user = User(
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            full_name=profile.get("name"),
            email_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    tokens = _issue(db, user)
    fragment = urlencode({"access_token": tokens.access_token, "refresh_token": tokens.refresh_token})
    response = RedirectResponse(f"{settings.FRONTEND_URL}/#{fragment}")
    response.delete_cookie(oauth_state_cookie)
    return response


@router.post("/password-reset/request", status_code=202)
def request_password_reset(data: PasswordResetRequest, db: Session = Depends(get_db)):
    if not settings.SMTP_HOST or not settings.SMTP_FROM:
        raise HTTPException(503, "Email delivery is not configured")
    user = db.scalar(select(User).where(User.email == str(data.email).lower(), User.is_active.is_(True)))
    if not user:
        return {"message": "If this email is registered, password reset instructions will be sent."}
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    db.query(PasswordReset).filter(PasswordReset.user_id == user.id).delete()
    db.add(PasswordReset(
        token_hash=token_hash,
        user_id=user.id,
        expires_at=utcnow() + timedelta(minutes=30),
    ))
    reset_url = f"{settings.FRONTEND_URL}/?reset_token={quote(token)}"
    message = EmailMessage()
    message["Subject"] = "Сброс пароля Kochmon"
    message["From"] = settings.SMTP_FROM
    message["To"] = user.email
    message.set_content(f"Чтобы задать новый пароль, откройте ссылку в течение 30 минут:\n{reset_url}")
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            if settings.SMTP_STARTTLS:
                smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        db.rollback()
        raise HTTPException(502, "Password reset email could not be sent") from exc
    db.commit()
    return {"message": "If this email is registered, password reset instructions will be sent."}


@router.post("/password-reset/confirm", status_code=204)
def confirm_password_reset(data: PasswordResetConfirm, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(data.token.encode()).hexdigest()
    reset = db.get(PasswordReset, token_hash)
    if not reset or reset.used or reset.expires_at <= utcnow():
        raise HTTPException(400, "Invalid or expired reset token")
    user = db.get(User, reset.user_id)
    if not user or not user.is_active:
        raise HTTPException(400, "Invalid or expired reset token")
    user.password_hash = hash_password(data.password)
    reset.used = True
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked=True))
    db.commit()
    return Response(status_code=204)
