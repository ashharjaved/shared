# src/healthcare/infrastructure/models.py
"""
Healthcare domain models.
Contains:
- Patient (healthcare recipients)
- Doctor (healthcare providers)
- Appointment (scheduled consultations)
Important:
- PHI is stored here (protected by RLS)
- Appointment status transitions are business-critical
"""
from uuid import UUID
from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import ForeignKey, text, String, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM

from shared.database import Base

class Patient(Base):
    """Healthcare patient record."""
    __tablename__ = 'patients'
    
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey('tenants.id'), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    medical_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(nullable=True)
    emergency_contact: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Relationships
    appointments: Mapped[List['Appointment']] = relationship(back_populates='patient')
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'phone_number', name='uq_patients__tenant_phone'),
        CheckConstraint("phone_number ~ '^\\+[1-9]\\d{1,14}$'", name='chk_patients__phone_e164'),
    )

class Doctor(Base):
    """Healthcare provider with availability schedule."""
    __tablename__ = 'doctors'
    
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey('tenants.id'), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    specialization: Mapped[str] = mapped_column(String(100), nullable=False)
    availability_schedule: Mapped[dict] = mapped_column(JSONB, nullable=False)
    consultation_duration: Mapped[int] = mapped_column(nullable=False, server_default=text('30'))
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text('true'))
    created_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Relationships
    appointments: Mapped[List['Appointment']] = relationship(back_populates='doctor')
    
    __table_args__ = (
        CheckConstraint('consultation_duration > 0', name='chk_doctors__duration_positive'),
    )

class Appointment(Base):
    """Scheduled healthcare consultation."""
    __tablename__ = 'appointments'
    
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey('tenants.id'), nullable=False)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey('patients.id'), nullable=False)
    doctor_id: Mapped[UUID] = mapped_column(ForeignKey('doctors.id'), nullable=False)
    service_type: Mapped[str] = mapped_column(String(100), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(nullable=False)
    duration_minutes: Mapped[int] = mapped_column(nullable=False, server_default=text('30'))
    status: Mapped[str] = mapped_column(ENUM('SCHEDULED', 'CONFIRMED', 'CANCELLED', 'COMPLETED', 'NO_SHOW', name='appointment_status_enum'), nullable=False, server_default='SCHEDULED')
    confirmation_status: Mapped[str] = mapped_column(ENUM('PENDING', 'CONFIRMED', 'DECLINED', name='confirmation_status_enum'), nullable=False, server_default='PENDING')
    queue_position: Mapped[Optional[int]] = mapped_column(nullable=True)
    appointment_fee: Mapped[Optional[float]] = mapped_column(nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Relationships
    patient: Mapped['Patient'] = relationship(back_populates='appointments')
    doctor: Mapped['Doctor'] = relationship(back_populates='appointments')
    
    __table_args__ = (
        CheckConstraint('duration_minutes > 0', name='chk_appointments__duration'),
        CheckConstraint('scheduled_at > now()', name='chk_appointments__future'),
        CheckConstraint(
            "tenant_id = (SELECT tenant_id FROM patients p WHERE p.id = patient_id) "
            "AND tenant_id = (SELECT tenant_id FROM doctors d WHERE d.id = doctor_id)",
            name='fk_appointments__tenant_match'
        ),
        Index('ix_appt__patient_scheduled', 'patient_id', 'scheduled_at'),
        # Index('ix_appt__patient_scheduled', 'patient_id', 'scheduled_at', postgresql_desc=True),
        Index('ix_appt__doctor_scheduled', 'doctor_id', 'scheduled_at'),
        Index('ix_appt__tenant_status_date', 'tenant_id', 'status', 'scheduled_at'),
    )

__all__ = ['Patient', 'Doctor', 'Appointment']