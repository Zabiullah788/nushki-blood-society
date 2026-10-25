import os
import urllib.parse
import traceback
from datetime import datetime, date, timedelta, timezone
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

# --- EMERGENCY ACTIONS: POST, RESOLVE & DELETE ---

@app.post("/requests", response_class=responses.RedirectResponse)
@app.post("/requests/", response_class=responses.RedirectResponse)
def handle_create_request(
    patient_name: str = Form(...),
    blood_group: str = Form(...),
    units_needed: int = Form(...),
    hospital: str = Form(...),
    contact_number: str = Form(...),
    expiry_hours: int = Form(2),
    notes: str = Form("")
):
    try:
        # Calculate exact expiry timestamp in UTC
        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(hours=int(expiry_hours))

        supabase.table("blood_requests").insert({
            "patient_name": patient_name.strip(),
            "blood_group": blood_group.strip().replace(" ", "+"),
            "units_needed": units_needed,
            "hospital": hospital.strip(),
            "contact_number": contact_number.strip(),
            "required_by_time": f"{expiry_hours} Hours",
            "notes": notes.strip(),
            "status": "OPEN",
            "created_at": now_utc.isoformat()
        }).execute()
    except Exception as e:
        print("ERROR saving blood request:", repr(e))

    return responses.RedirectResponse(url="/?tab=requests", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/requests/resolve", response_class=responses.RedirectResponse)
def handle_resolve_request(request_id: str = Form(...)):
    try:
        supabase.table("blood_requests").update({"status": "FULFILLED"}).eq("id", request_id).execute()
    except Exception as e:
        print("Error resolving request:", e)
    return responses.RedirectResponse(url="/?tab=requests", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/requests/delete", response_class=responses.RedirectResponse)
def handle_delete_request(request_id: str = Form(...)):
    try:
        supabase.table("blood_requests").delete().eq("id", request_id).execute()
    except Exception as e:
        print("Error deleting request:", e)
    return responses.RedirectResponse(url="/?tab=requests", status_code=status.HTTP_303_SEE_OTHER)


# --- DONOR REGISTRATION ---

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
        clean_date = last_donated_date.strip() if (last_donated_date and last_donated_date.strip()) else None
        clean_group = blood_group.strip().replace(" ", "+")

        supabase.table("profiles").insert({
            "full_name": full_name.strip(),
            "blood_group": clean_group,
            "phone_number": phone_number.strip(),
            "area_nushki": area_nushki.strip(),
            "last_donated_date": clean_date,
            "is_available": True
        }).execute()
    except Exception as e:
        print("ERROR saving donor to Supabase:", repr(e))

    return responses.RedirectResponse(url="/?tab=donors", status_code=status.HTTP_303_SEE_OTHER)


# --- DASHBOARD VIEW ---

@app.get("/")
def render_dashboard(request: Request, tab: str = "requests", group: str = "ALL", error: str = None):
    try:
        admin_status = is_admin_logged_in(request)
        
        # Normalize blood group filter (turns "B " into "B+")
        normalized_group = group.strip().replace(" ", "+") if group else "ALL"

        # 1. Fetch & Auto-Expire Requests
        active_requests = []
        try:
            req_res = supabase.table("blood_requests").select("*").order("created_at", desc=True).execute()
            raw_requests = req_res.data or []
            now_utc = datetime.now(timezone.utc)

            for br in raw_requests:
                # Check creation time to see if 1+ hours expired
                created_str = br.get("created_at")
                hours_limit = 2
                req_time_str = br.get("required_by_time", "2 Hours")
                try:
                    hours_limit = int(''.join(filter(str.isdigit, req_time_str)) or 2)
                except Exception:
                    hours_limit = 2

                if created_str:
                    try:
                        created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                        expiry_dt = created_dt + timedelta(hours=hours_limit)
                        
                        if now_utc > expiry_dt:
                            # Auto-delete expired request from database
                            supabase.table("blood_requests").delete().eq("id", br.get("id")).execute()
                            continue
                        else:
                            diff = expiry_dt - now_utc
                            mins_left = int(diff.total_seconds() // 60)
                            if mins_left < 60:
                                br["time_left_str"] = f"{mins_left} mins remaining"
                            else:
                                br["time_left_str"] = f"{mins_left // 60}h {mins_left % 60}m"
                    except Exception:
                        br["time_left_str"] = req_time_str
                else:
                    br["time_left_str"] = req_time_str

                if br.get("status") == "OPEN":
                    active_requests.append(br)
        except Exception as e:
            print("Error fetching requests:", e)

        # 2. Fetch Donors with Exact Blood Group Matching
        donors = []
        try:
            donor_query = supabase.table("profiles").select("*")
            if normalized_group != "ALL":
                donor_query = donor_query.eq("blood_group", normalized_group)
            
            donors_res = donor_query.order("full_name").execute()
            raw_donors = donors_res.data or []

            for d in raw_donors:
                is_eligible, status_msg = calculate_donor_eligibility(d.get("last_donated_date"))
                d["is_available"] = is_eligible and d.get("is_available", True)
                d["availability_text"] = status_msg
                donors.append(d)
        except Exception as e:
            print("Error fetching donors:", e)

        # 3. Fetch Core Team
        try:
            team_res = supabase.table("society_team").select("*").eq("is_active", True).order("display_order").execute()
            team_members = team_res.data or []
        except Exception:
            team_members = []

        # 4. WhatsApp instant alert dispatches
        for br in active_requests:
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
                    f"Required: {br.get('time_left_str')}\n"
                    f"Attendant Contact: {br.get('contact_number')}\n\n"
                    f"Please contact immediately if available to donate."
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
            "selected_group": normalized_group,
            "blood_requests": active_requests,
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