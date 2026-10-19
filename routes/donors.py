from fastapi import APIRouter, Form, status
from fastapi.responses import RedirectResponse
from database import supabase

router = APIRouter(prefix="/donors", tags=["Donors"])

@router.post("/register")
def register_donor(
    full_name: str = Form(...),
    blood_group: str = Form(...),
    phone_number: str = Form(...),
    area_nushki: str = Form("Station Road")
):
    supabase.table("profiles").insert({
        "full_name": full_name,
        "blood_group": blood_group,
        "phone_number": phone_number,
        "area_nushki": area_nushki,
        "is_available": True
    }).execute()
    return RedirectResponse(url="/?tab=donors", status_code=status.HTTP_303_SEE_OTHER)