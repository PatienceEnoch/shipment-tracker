from pydantic import BaseModel


class EmailPayload(BaseModel):
    sender: str | None = None
    subject: str = ""
    text: str = ""
    message_id: str | None = None


class FedExEvent(BaseModel):
    tracking_number: str
    event: str
