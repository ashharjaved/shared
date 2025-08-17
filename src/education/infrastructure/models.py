# src/education/infrastructure/models.py
"""
Education domain models.
Contains:
- Student (education recipients)
- FeeRecord (financial obligations)
Important:
- Fee status transitions are business-critical
- Student records contain sensitive information (protected by RLS)
"""
from uuid import UUID
from datetime import datetime, date
from typing import Optional

from sqlalchemy import ForeignKey, text, String, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM

from shared.database import Base

class Student(Base):
    """Education student record."""
    __tablename__ = 'students'
    
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey('tenants.id'), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    student_id_number: Mapped[str] = mapped_column(String(50), nullable=False)
    class_grade: Mapped[str] = mapped_column(String(20), nullable=False)
    parent_contact: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    enrollment_date: Mapped[date] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text('true'))
    created_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Relationships
    fee_records: Mapped[List['FeeRecord']] = relationship(back_populates='student')
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'phone_number', name='uq_students__tenant_phone'),
        UniqueConstraint('tenant_id', 'student_id_number', name='uq_students__tenant_sid'),
    )

class FeeRecord(Base):
    """Student financial obligation record."""
    __tablename__ = 'fee_records'
    
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey('tenants.id'), nullable=False)
    student_id: Mapped[UUID] = mapped_column(ForeignKey('students.id'), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(10), nullable=False)
    fee_type: Mapped[str] = mapped_column(ENUM('TUITION', 'TRANSPORT', 'LIBRARY', 'EXAMINATION', 'MISCELLANEOUS', name='fee_type_enum'), nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False)
    due_date: Mapped[date] = mapped_column(nullable=False)
    paid_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    paid_amount: Mapped[float] = mapped_column(nullable=False, server_default=text('0'))
    payment_method: Mapped[Optional[str]] = mapped_column(ENUM('CASH', 'BANK_TRANSFER', 'ONLINE', 'CHEQUE', name='payment_method_enum'), nullable=True)
    late_fee: Mapped[float] = mapped_column(nullable=False, server_default=text('0'))
    status: Mapped[str] = mapped_column(ENUM('PENDING', 'PAID', 'OVERDUE', name='fee_status_enum'), nullable=False, server_default='PENDING')
    created_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Relationships
    student: Mapped['Student'] = relationship(back_populates='fee_records')
    
    __table_args__ = (
        CheckConstraint('amount >= 0 AND paid_amount >= 0 AND late_fee >= 0', name='chk_fee__nonneg'),
        CheckConstraint(
            "tenant_id = (SELECT tenant_id FROM students s WHERE s.id = student_id)",
            name='fk_fee__tenant_match'
        ),
        Index('ix_fee__student_year', 'student_id', 'academic_year', postgresql_desc=True),
        Index('ix_fee__due_status', 'due_date', 'status', postgresql_where=text("status IN ('PENDING','OVERDUE')")),
        Index('ix_fee__tenant_status_due', 'tenant_id', 'status', 'due_date'),
    )

__all__ = ['Student', 'FeeRecord']