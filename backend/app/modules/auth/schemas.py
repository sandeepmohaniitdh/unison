from pydantic import BaseModel, EmailStr, Field


class SignupIn(BaseModel):
    name: str = Field(min_length=1, max_length=120, examples=["Km Shristi Singh"])
    email: EmailStr = Field(examples=["cs26mt011@iitdh.ac.in"])
    password: str = Field(min_length=8, max_length=128)
    consent: bool = Field(description="The data notice was shown and accepted.")
    invitation_token: str | None = Field(
        None,
        description="When signing up from an invitation link. Staff invitations give their role, "
        "and the invited email counts as verified.",
    )


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200, description="The token from the emailed link.")


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)


class AuthConfig(BaseModel):
    google_enabled: bool
    allowed_email_domain: str
    auth_mode: str = Field(description="'session' on the real site; 'demo' allows the X-Demo-User header.")
    csrf_header: str = Field(description="Header that state-changing requests with the cookie must send.")


class Accepted(BaseModel):
    message: str


class VerifiedOut(BaseModel):
    email: str
    message: str
