# routes/requests.py
from fastapi import APIRouter, Form, Request, status, HTTPException
from fastapi.responses import RedirectResponse
from database import supabase
from routes.auth import is_admin_logged_in

router = APIRouter(prefix="/requests", tags=["Requests"])

# Anyone can submit a request
@router.post("/new")
def create_blood_request(
    patient_name: str = Form(...),
    blood_group: str = Form(...),
    units_needed: int = Form(...),
    hospital: str = Form("DHQ Hospital Nushki"),
    contact_number: str = Form(...),
    required_by_time: str = Form(...),
    notes: str = Form("")
):
    supabase.table("blood_requests").insert({
        "patient_name": patient_name,
        "blood_group": blood_group,
        "units_needed": units_needed,
        "units_fulfilled": 0,
        "hospital": hospital,
        "contact_number": contact_number,
        "required_by_time": required_by_time,
        "notes": notes,
        "status": "OPEN"
    }).execute()
    return RedirectResponse(url="/?tab=requests", status_code=status.HTTP_303_SEE_OTHER)

# Admin only: Mark fulfilled
@router.post("/{request_id}/fulfill")
def mark_fulfilled(request: Request, request_id: str):
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/?tab=login", status_code=status.HTTP_303_SEE_OTHER)
    supabase.table("blood_requests").update({"status": "FULFILLED"}).eq("id", request_id).execute()
    return RedirectResponse(url="/?tab=requests", status_code=status.HTTP_303_SEE_OTHER)

# Admin only: Delete request
@router.post("/{request_id}/delete")
def delete_request(request: Request, request_id: str):
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/?tab=login", status_code=status.HTTP_303_SEE_OTHER)
    supabase.table("blood_requests").delete().eq("id", request_id).execute()
    return RedirectResponse(url="/?tab=requests", status_code=status.HTTP_303_SEE_OTHER)