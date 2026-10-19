# routes/auth.py
import os
from fastapi import APIRouter, Form, Request, status
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/auth", tags=["Auth"])

ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "admin123")
SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "fallback-secret-key-321")

serializer = URLSafeTimedSerializer(SECRET_KEY)

def is_admin_logged_in(request: Request) -> bool:
    """Helper to check if the browser has a valid admin session cookie."""
    cookie = request.cookies.get("admin_session")
    if not cookie:
        return False
    try:
        user = serializer.loads(cookie, max_age=86400 * 7) # Valid for 7 days
        return user == ADMIN_USER
    except Exception:
        return False

@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USER and password == ADMIN_PASS:
        token = serializer.dumps(ADMIN_USER)
        response = RedirectResponse(url="/?tab=requests", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            key="admin_session",
            value=token,
            httponly=True,
            max_age=86400 * 7,
            samesite="lax"
        )
        return response
    
    # If invalid credentials, redirect back to login modal
    return RedirectResponse(url="/?tab=login&error=invalid", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/logout")
def logout():
    response = RedirectResponse(url="/?tab=requests", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("admin_session")
    return response