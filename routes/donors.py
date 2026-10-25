from fastapi import APIRouter, Form, responses, status
from database import supabase

router = APIRouter(prefix="/requests", tags=["requests"])

@router.post("", response_class=responses.RedirectResponse)
@router.post("/", response_class=responses.RedirectResponse)
def create_request(
    patient_name: str = Form(...),
    blood_group: str = Form(...),
    units_needed: int = Form(...),
    hospital: str = Form(...),
    contact_number: str = Form(...),
    required_by_time: str = Form(...),
    notes: str = Form("")
):
    try:
        supabase.table("blood_requests").insert({
            "patient_name": patient_name,
            "blood_group": blood_group,
            "units_needed": units_needed,
            "hospital": hospital,
            "contact_number": contact_number,
            "required_by_time": required_by_time,
            "notes": notes,
            "status": "OPEN"
        }).execute()
    except Exception as e:
        print("Error creating request:", e)

    return responses.RedirectResponse(url="/?tab=requests", status_code=status.HTTP_303_SEE_OTHER)