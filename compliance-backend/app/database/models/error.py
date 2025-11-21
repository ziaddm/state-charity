from sqlalchemy import Column, String, Integer, Text, ForeignKey
from .base import Base

class ValidationError(Base):
    __tablename__ = "validation_errors"
    
    id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    error_code = Column(String)
    severity = Column(String)
    field_name = Column(String)
    row_number = Column(Integer)
    message = Column(Text)
    value = Column(String)