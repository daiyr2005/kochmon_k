from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.models import ListingStatus, Role


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(ORM):
    id: int
    email: EmailStr
    full_name: str | None
    phone: str | None
    role: Role
    email_verified: bool
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=32)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class NotificationPreferencesIn(BaseModel):
    new_listings_by_category: bool
    new_objects_in_city: bool
    saved_price_change: bool
    inquiry_replies: bool
    booking_updates: bool
    booking_reminders: bool


class NotificationPreferencesOut(NotificationPreferencesIn):
    pass


class CountryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=2, max_length=3)


class CountryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    code: str | None = Field(default=None, min_length=2, max_length=3)


class CountryOut(ORM, CountryIn):
    id: int


class CityIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    country_id: int


class CityPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    country_id: int | None = None


class CityOut(ORM, CityIn):
    id: int
    country: CountryOut


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: int | None = None


class CategoryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    parent_id: int | None = None


class CategoryOut(ORM, CategoryIn):
    id: int


class CategoryNode(BaseModel):
    id: int
    name: str
    children: list["CategoryNode"] = []


class ListingIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=10000)
    kind: str = Field(default="Аренда", min_length=1, max_length=32)
    contact_phone: str | None = Field(default=None, max_length=32)
    photo_url: str | None = Field(default=None, max_length=500)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="KGS", min_length=3, max_length=3)
    category_id: int
    city_id: int


class ListingPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    kind: str | None = Field(default=None, min_length=1, max_length=32)
    contact_phone: str | None = Field(default=None, max_length=32)
    photo_url: str | None = Field(default=None, max_length=500)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    category_id: int | None = None
    city_id: int | None = None


class ListingOut(ORM):
    id: int
    owner_id: int
    category_id: int
    city_id: int
    category: CategoryOut
    city: CityOut
    title: str
    description: str
    kind: str
    contact_phone: str | None
    photo_url: str | None
    price: Decimal
    currency: str
    status: ListingStatus
    created_at: datetime
    updated_at: datetime


class Page(BaseModel):
    items: list[ListingOut]
    total: int
    page: int
    size: int


class SearchIn(BaseModel):
    country: str | None = None
    city: str | None = None
    price_min: Decimal | None = Field(default=None, ge=0)
    price_max: Decimal | None = Field(default=None, ge=0)
    extra: list[str] = Field(default_factory=list)
    image_base64: str | None = Field(default=None, max_length=12_000_000)
    image_mime_type: str | None = None


class ChatIn(BaseModel):
    message: str = Field(default="", max_length=4000)
    conversation_id: str | None = None
    image_base64: str | None = Field(default=None, max_length=12_000_000)
    image_mime_type: str | None = None


class CampaignIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    city: str = Field(min_length=1, max_length=120)
    kind: str = Field(min_length=1, max_length=32, alias="type")
    placement: str = Field(min_length=1, max_length=120)
    days: int = Field(ge=1, le=365)
    description: str = Field(default="", max_length=10000)
    contact_phone: str = Field(min_length=5, max_length=32, alias="phone")
    photo_url: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(populate_by_name=True)


class CampaignOut(ORM):
    id: int
    title: str
    city: str
    description: str
    photo_url: str | None
    status: str
    created_at: datetime


class WhatsappLinkIn(BaseModel):
    phone: str = Field(min_length=8, max_length=32)


class WhatsappVerifyIn(BaseModel):
    challenge_id: str
    code: str = Field(min_length=6, max_length=6)
