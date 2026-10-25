import os
import urllib.parse
import traceback
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

# Register Auth router
app.include_router(auth_routes.router)

MOCK_REQUESTS = [
    {
        "id": "1",
        "patient_name": "Haji Abdul Rasheed",
        "blood_group": "B+",
        "units_needed": 2,
        "hospital": "DHQ Hospital Nushki (Emergency)",
        "contact_number": "03337890123",
        "required_by_time": "Within 2 Hours",
        "notes": "Emergency surgery delivery case",
        "status": "OPEN",
    }
]

MOCK_DONORS = [
    {"full_name": "Muhammad Asif", "blood_group": "B+", "area_nushki": "Station Road", "phone_number": "03331234567", "is_available": True},
    {"full_name": "Farooq Jamaldini", "blood_group": "O-", "area_nushki": "Killi Jamaldini", "phone_number": "03009876543", "is_available": True},
    {"full_name": "Bilal Mengal", "blood_group": "A+", "area_nushki": "Killi Mengal", "phone_number": "03214567890", "is_available": True},
    {"full_name": "Zubair Ahmed", "blood_group": "B+", "area_nushki": "Bypass Nushki", "phone_number": "03456789012", "is_available": False},
]

MOCK_TEAM = [
    {"full_name": "Dr. Tariq Baloch", "role_title": "President", "area": "Civil Hospital Road", "phone_number": "03330001111"},
    {"full_name": "Mir Sanaullah Mengal", "role_title": "General Secretary", "area": "Killi Mengal", "phone_number": "03330002222"},
    {"full_name": "Engr. Naveed Badini", "role_title": "Emergency Coordinator", "area": "Station Road", "phone_number": "03330003333"},
]

# --- FORM SUBMISSIONS ---

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
        res = supabase.table("blood_requests").insert({
            "patient_name": patient_name,
            "blood_group": blood_group,
            "units_needed": units_needed,
            "hospital": hospital,
            "contact_number": contact_number,
            "required_by_time": required_by_time,
            "notes": notes,
            "status": "OPEN"
        }).execute()
        print("Insert request success:", res)
    except Exception as e:
        print("ERROR saving blood request to Supabase:", repr(e))

    return responses.RedirectResponse(url="/?tab=requests", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/donors", response_class=responses.RedirectResponse)
@app.post("/donors/", response_class=responses.RedirectResponse)
def handle_register_donor(
    full_name: str = Form(...),
    blood_group: str = Form(...),
    phone_number: str = Form(...),
    area_nushki: str = Form(...)
):
    try:
        res = supabase.table("profiles").insert({
            "full_name": full_name,
            "blood_group": blood_group,
            "phone_number": phone_number,
            "area_nushki": area_nushki,
            "is_available": True
        }).execute()
        print("Insert donor success:", res)
    except Exception as e:
        print("ERROR saving donor to Supabase:", repr(e))

    return responses.RedirectResponse(url="/?tab=donors", status_code=status.HTTP_303_SEE_OTHER)


# --- DASHBOARD VIEW ---

@app.get("/")
def render_dashboard(request: Request, tab: str = "requests", group: str = "ALL", error: str = None):
    try:
        admin_status = is_admin_logged_in(request)

        # 1. Fetch Requests
        try:
            req_res = supabase.table("blood_requests").select("*").order("created_at", desc=True).execute()
            blood_requests = req_res.data or []
        except Exception as e:
            print("Supabase blood_requests fetch error:", repr(e))
            blood_requests = MOCK_REQUESTS

        # 2. Fetch Donors
        try:
            donor_query = supabase.table("profiles").select("*")
            if group and group != "ALL":
                donor_query = donor_query.eq("blood_group", group)
            donors_res = donor_query.order("full_name").execute()
            donors = donors_res.data or []
        except Exception as e:
            print("Supabase donors fetch error:", repr(e))
            if group and group != "ALL":
                donors = [d for d in MOCK_DONORS if d["blood_group"] == group]
            else:
                donors = MOCK_DONORS

        # 3. Fetch Core Team
        try:
            team_res = supabase.table("society_team").select("*").eq("is_active", True).order("display_order").execute()
            team_members = team_res.data or []
        except Exception as e:
            print("Supabase society_team fetch error:", repr(e))
            team_members = MOCK_TEAM

        # 4. WhatsApp instant alert generation
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

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context=context
        )

    except Exception:
        from fastapi.responses import HTMLResponse
        return HTMLResponse(
            f"<h3>Error rendering page:</h3><pre>{traceback.format_exc()}</pre>",
            status_code=500
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)