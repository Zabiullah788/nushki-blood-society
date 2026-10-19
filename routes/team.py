# routes/team.py
from fastapi import APIRouter, Form, Request, status
from fastapi.responses import RedirectResponse
from database import supabase
from routes.auth import is_admin_logged_in

router = APIRouter(prefix="/team", tags=["Team"])

# Admin only: Add team member
@router.post("/add")
def add_team_member(
    request: Request,
    full_name: str = Form(...),
    role_title: str = Form(...),
    phone_number: str = Form(...),
    area: str = Form("Nushki City")
):
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/?tab=login", status_code=status.HTTP_303_SEE_OTHER)

    supabase.table("society_team").insert({
        "full_name": full_name,
        "role_title": role_title,
        "phone_number": phone_number,
        "area": area,
        "is_active": True
    }).execute()
    return RedirectResponse(url="/?tab=team", status_code=status.HTTP_303_SEE_OTHER)