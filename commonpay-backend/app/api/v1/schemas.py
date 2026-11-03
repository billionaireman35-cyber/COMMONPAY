from decimal import Decimal
from pydantic import BaseModel, EmailStr, Field, field_validator


class CheckoutRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=5)
    customer_email: EmailStr
    provider: str
    description: str = Field(min_length=2, max_length=200)
    callback_url: str

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value):
        return value.upper()

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value):
        value = value.lower()
        if value not in {"flutterwave", "paystack"}:
            raise ValueError("Unsupported provider.")
        return value


class AIQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class AIActionRequest(BaseModel):
    action: str
    summary: str = Field(min_length=1, max_length=1000)
