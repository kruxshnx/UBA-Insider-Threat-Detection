from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal

# --- CERT-like Dataset Schema Definitions ---

class LogonEvent(BaseModel):
    """Schema for Logon/Logoff events."""
    id: str = Field(..., description="Unique Event ID")
    user: str = Field(..., description="User ID (e.g., U101)")
    date: datetime = Field(..., description="Timestamp")
    pc: str = Field(..., description="Machine ID")
    activity: Literal["Logon", "Logoff"]

class FileEvent(BaseModel):
    """Schema for File access events."""
    id: str
    user: str
    date: datetime
    pc: str
    filename: str
    activity: Literal["File Open", "File Copy", "File Delete", "File Write"]
    to_removable_media: bool = Field(False, description="True if copied to USB/External")

class HttpEvent(BaseModel):
    """Schema for Web browsing events."""
    id: str
    user: str
    date: datetime
    pc: str
    url: str
    content: Optional[str] = None

class DeviceEvent(BaseModel):
    """Schema for USB/Device connection events."""
    id: str
    user: str
    date: datetime
    pc: str
    activity: Literal["Connect", "Disconnect"]

# --- Validation Helper ---
def validate_schema(data: dict, event_type: str) -> bool:
    try:
        if event_type == "logon":
            LogonEvent(**data)
        elif event_type == "file":
            FileEvent(**data)
        elif event_type == "http":
            HttpEvent(**data)
        elif event_type == "device":
            DeviceEvent(**data)
        return True
    except Exception as e:
        return False
