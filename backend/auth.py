"""Minimal demo authentication: pick a user, enter the password, receive an HMAC-signed token.
Demo rule: the password is the user's first name (not case-sensitive), so nothing is stored."""
import base64
import hashlib
import hmac

from fastapi import Depends, Header, HTTPException

from .config import APP_SECRET
from .db import fetch_one


def _sig(user_id: str) -> str:
    return hmac.new(APP_SECRET.encode(), user_id.encode(), hashlib.sha256).hexdigest()[:32]


def make_token(user_id: str) -> str:
    return base64.urlsafe_b64encode(f"{user_id}.{_sig(user_id)}".encode()).decode()


def check_password(full_name: str, password: str) -> bool:
    return hmac.compare_digest(full_name.split()[0].lower().encode(), password.strip().lower().encode())


def current_user(authorization: str = Header(default="")):
    try:
        user_id, sig = base64.urlsafe_b64decode(authorization.removeprefix("Bearer ").encode()).decode().split(".")
    except Exception:
        raise HTTPException(401, "Please sign in")
    if not hmac.compare_digest(sig, _sig(user_id)):
        raise HTTPException(401, "Invalid session")
    user = fetch_one("SELECT * FROM app_users WHERE user_id = %s AND is_active", (user_id,))
    if not user:
        raise HTTPException(401, "Unknown user")
    return user


def admin(user=Depends(current_user)):
    if user["app_role"] != "admin":
        raise HTTPException(403, "Only the admin can do this")
    return user


def manager(user=Depends(current_user)):
    if user["app_role"] != "manager" or not user["employee_id"]:
        raise HTTPException(403, "Only managers can approve assignments")
    return user
