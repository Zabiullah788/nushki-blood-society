import os
import urllib.parse
import traceback
from datetime import datetime, date, timedelta
from fastapi import FastAPI, Request, Form, responses, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import supabase
from models import BLOOD_COMPATIBILITY
from routes import auth as auth_routes
from routes.auth import is_admin_logged_in

app = FastAPI(title="Blood Donation Society Nushki")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_path = os.path.join(BASE_DIR, "static")
templates_path = os.path.join(BASE_DIR, "templates")

if not os.path.exists(static_path):
    os.makedirs(static_path, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_path), name="static")
templates = Jinja2Templates(directory=templates_path)

app.include_router(auth_routes.router)

# Helper function to check 90-day eligibility
def calculate_donor_eligibility(last_date_str):
    if not last_date_str:
        return True, "Never donated / Ready now"
    try:
        last_date = datetime.strptime(str(last_date_str)[:10], "%Y-%m-%d").date()
        eligible_date = last_date + timedelta(days=90)
        today = date.today()
        if today >= eligible_date:
            return True, "Eligible to donate"
        else:
            days_left = (eligible_date - today).days
            return False, f"Available in {days_left} days ({eligible_date.strftime('%b %d')})"
    except Exception:
        return True, "Ready"

MOCK_DONORS = [
    {"full_name": "Muhammad Asif", "blood_group": "B+", "area_nushki": "Station Road", "phone_number": "03331234567", "is_available": True, "availability_text": "Eligible to donate"},
    {"full_name": "Farooq Jamaldini", "blood_group": "O-", "area_nushki": "Killi Jamaldini", "phone_number": "03009876543", "is_available": True, "availability_text": "Eligible to donate"},
    {"full_name": "Bilal Mengal", "blood_group": "A+", "area_nushki": "Killi Mengal", "phone_number": "03214567890", "is_available": True, "availability_text": "Eligible to donate"},
    {"full_name": "Zubair Ahmed", "blood_group": "B+", "area_nushki": "Bypass Nushki", "phone_number": "03456789012", "is_available": False, "availability_text": "Available in 24 days"},
]

@app.post("/donors", response_class=responses.RedirectResponse)
@app.post("/donors/", response_class=responses.RedirectResponse)
def handle_register_donor(
    full_name: str = Form(...),
    blood_group: str = Form(...),
    phone_number: str = Form(...),
    area_nushki: str = Form(...),
    last_donated_date: str = Form(None)
):
    try:
        # Normalize empty date field to None
        clean_date = last_donated_date.strip() if (last_donated_date and last_donated_date.strip()) else None

        supabase.table("profiles").insert({
            "full_name": full_name,
            "blood_group": blood_group,
            "phone_number": phone_number,
            "area_nushki": area_nushki,
            "last_donated_date": clean_date,
            "is_available": True
        }).execute()
    except Exception as e:
        print("ERROR saving donor to Supabase:", repr(e))

    return responses.RedirectResponse(url="/?tab=donors", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/requests", response_class=responses.RedirectResponse)
@app.post("/requests/", response_class=responses.RedirectResponse)
def handle_create_request(
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
        print("ERROR saving blood request:", repr(e))

    return responses.RedirectResponse(url="/?tab=requests", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/")
def render_dashboard(request: Request, tab: str = "requests", group: str = "ALL", error: str = None):
    try:
        admin_status = is_admin_logged_in(request)

        # 1. Fetch Requests
        try:
            req_res = supabase.table("blood_requests").select("*").order("created_at", desc=True).execute()
            blood_requests = req_res.data or []
        except Exception:
            blood_requests = []

        # 2. Fetch Donors & evaluate 90-day cooldown
        try:
            donor_query = supabase.table("profiles").select("*")
            if group and group != "ALL":
                donor_query = donor_query.eq("blood_group", group)
            donors_res = donor_query.order("full_name").execute()
            donors = donors_res.data or []

            for d in donors:
                is_eligible, status_msg = calculate_donor_eligibility(d.get("last_donated_date"))
                d["is_available"] = is_eligible and d.get("is_available", True)
                d["availability_text"] = status_msg
        except Exception:
            donors = MOCK_DONORS

        # 3. Fetch Core Team
        try:
            team_res = supabase.table("society_team").select("*").eq("is_active", True).order("display_order").execute()
            team_members = team_res.data or []
        except Exception:
            team_members = []

        # 4. WhatsApp instant alert dispatches
        for br in blood_requests:
            matched_groups = BLOOD_COMPATIBILITY.get(br.get("blood_group", "O+"), [br.get("blood_group", "O+")])
            matched_donors = [d for d in donors if d.get("blood_group") in matched_groups and d.get("is_available")]
            br["matched_count"] = len(matched_donors)
            br["dispatches"] = []
            for d in matched_donors:
                msg = (
                    f"🚨 *URGENT BLOOD APPEAL - Nushki*\n"
                    f"Patient: {br.get('patient_name')}\n"
                    f"Group: *{br.get('blood_group')}* ({br.get('units_needed')} units)\n"
                    f"Hospital: {br.get('hospital')}\n"
                    f"Required By: {br.get('required_by_time')}\n"
                    f"Attendant Contact: {br.get('contact_number')}\n\n"
                    f"Please reply or reach hospital immediately if you can donate."
                )
                encoded = urllib.parse.quote(msg)
                br["dispatches"].append({
                    "name": d.get("full_name"),
                    "group": d.get("blood_group"),
                    "wa_url": f"https://wa.me/{d.get('phone_number')}?text={encoded}"
                })

        context = {
            "request": request,
            "active_tab": tab,
            "selected_group": group,
            "blood_requests": blood_requests,
            "donors": donors,
            "team_members": team_members,
            "is_admin": admin_status,
            "login_error": error
        }

        return templates.TemplateResponse(request=request, name="index.html", context=context)

    except Exception:
        from fastapi.responses import HTMLResponse
        return HTMLResponse(
            f"<h3>Error rendering page:</h3><pre>{traceback.format_exc()}</pre>",
            status_code=500
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)