from pydantic import BaseModel
from typing import Optional

# Universal red blood cell compatibility
BLOOD_COMPATIBILITY = {
    "A+":  ["A+", "A-", "O+", "O-"],
    "A-":  ["A-", "O-"],
    "B+":  ["B+", "B-", "O+", "O-"],
    "B-":  ["B-", "O-"],
    "AB+": ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
    "AB-": ["AB-", "A-", "B-", "O-"],
    "O+":  ["O+", "O-"],
    "O-":  ["O-"],
}

class BloodRequestCreate(BaseModel):
    patient_name: str
    blood_group: str
    units_needed: int
    hospital: str = "DHQ Hospital Nushki"
    contact_number: str
    required_by_time: str
    notes: Optional[str] = None