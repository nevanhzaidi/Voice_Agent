from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.connection import Base
import secrets


class Technician(Base):
    __tablename__ = "technicians"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    phone = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    service_areas = relationship("ServiceArea", back_populates="technician", cascade="all, delete-orphan")
    specialties = relationship("Specialty", back_populates="technician", cascade="all, delete-orphan")
    availability_slots = relationship("AvailabilitySlot", back_populates="technician", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="technician")


class ServiceArea(Base):
    __tablename__ = "service_areas"

    id = Column(Integer, primary_key=True, index=True)
    technician_id = Column(Integer, ForeignKey("technicians.id"), nullable=False)
    zip_code = Column(String(10), nullable=False, index=True)

    technician = relationship("Technician", back_populates="service_areas")


class Specialty(Base):
    __tablename__ = "specialties"

    id = Column(Integer, primary_key=True, index=True)
    technician_id = Column(Integer, ForeignKey("technicians.id"), nullable=False)
    appliance_type = Column(String(50), nullable=False)  # washer, dryer, refrigerator, etc.

    technician = relationship("Technician", back_populates="specialties")


class AvailabilitySlot(Base):
    __tablename__ = "availability_slots"

    id = Column(Integer, primary_key=True, index=True)
    technician_id = Column(Integer, ForeignKey("technicians.id"), nullable=False)
    day_of_week = Column(String(10), nullable=False)  # Monday, Tuesday, etc.
    date = Column(String(20), nullable=True)           # specific date YYYY-MM-DD
    start_time = Column(String(10), nullable=False)    # e.g., "09:00"
    end_time = Column(String(10), nullable=False)      # e.g., "17:00"
    is_booked = Column(Boolean, default=False)

    technician = relationship("Technician", back_populates="availability_slots")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    technician_id = Column(Integer, ForeignKey("technicians.id"), nullable=False)
    customer_name = Column(String(100), nullable=False)
    customer_phone = Column(String(20), nullable=True)
    customer_zip = Column(String(10), nullable=False)
    appliance_type = Column(String(50), nullable=False)
    issue_description = Column(Text, nullable=True)
    scheduled_date = Column(String(20), nullable=False)
    scheduled_time = Column(String(10), nullable=False)
    status = Column(String(20), default="confirmed")   # confirmed, cancelled, completed
    call_id = Column(String(100), nullable=True)       # Vapi call ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    technician = relationship("Technician", back_populates="appointments")


class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String(100), unique=True, nullable=False)
    caller_phone = Column(String(20), nullable=True)
    appliance_type = Column(String(50), nullable=True)
    zip_code = Column(String(10), nullable=True)
    customer_name = Column(String(100), nullable=True)
    conversation_summary = Column(Text, nullable=True)
    status = Column(String(20), default="in-progress")  # in-progress, completed, dropped
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    extra_data = Column(JSON, nullable=True)


class VisualUpload(Base):
    __tablename__ = "visual_uploads"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    call_id = Column(String(100), nullable=True, index=True)
    email = Column(String(255), nullable=False)
    status = Column(String(20), default="pending")  # pending, uploaded, analyzed, failed
    image_path = Column(String(500), nullable=True)
    analysis = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    uploaded_at = Column(DateTime(timezone=True), nullable=True)
    analyzed_at = Column(DateTime(timezone=True), nullable=True)

    @staticmethod
    def new_token() -> str:
        # URL-safe, short-ish, unguessable token
        return secrets.token_urlsafe(32)


