from datetime import datetime

from pydantic import BaseModel

from app.models.enums import AlertType, JobStatus


class AlertRecordResponse(BaseModel):
    id: int
    alert_type: AlertType
    status: JobStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentResponse(BaseModel):
    id: int
    started_at: datetime
    resolved_at: datetime | None
    created_at: datetime
    alert_jobs: list[AlertRecordResponse]

    model_config = {"from_attributes": True}
