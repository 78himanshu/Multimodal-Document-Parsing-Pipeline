from pydantic import BaseModel

class DataRecord(BaseModel):
    file_name: str
    key: str
    item: str
    data_type: str
    format: str
    length: int
    start: int
    end: int
    comments: str

class DataExtractionResponse(BaseModel):
    data_records: list[DataRecord]
