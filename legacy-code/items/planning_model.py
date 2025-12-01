from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class PlanningApplication(BaseModel):
    id: str
    url: str
    proposal: Optional[str] = None
    site_address: Optional[str] = None
    application_type: Optional[str] = None
    applicant_name: Optional[str] = None
    status: Optional[str] = None
    agent_name: Optional[str] = None
    officer_name: Optional[str] = None
    decision: Optional[str] = None
    decision_date: Optional[str] = None
    determination_level: Optional[str] = None
    valid_date: Optional[str] = None
    committee_date: Optional[str] = None
    consultation_expiry_date: Optional[str] = None
    application_expiry_date: Optional[str] = None
    planning_portal_reference: Optional[str] = None
    parishes: Optional[str] = None
    wards: Optional[str] = None
