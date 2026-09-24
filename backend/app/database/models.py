from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.database.connection import Base

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    booking_ref = Column(String(64), unique=True, index=True, nullable=False)
    pnr = Column(String(32), index=True, nullable=True)
    transaction_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Status: INITIATED, IN_PROGRESS, WAITING_MANUAL, PAYMENT_PENDING, CONFIRMED, FAILED, CANCELLED
    status = Column(String(32), default="INITIATED", index=True, nullable=False)
    
    # Journey details
    from_station = Column(String(64), nullable=False)
    to_station = Column(String(64), nullable=False)
    boarding_station = Column(String(64), nullable=True)
    journey_date = Column(Date, nullable=False)
    train_number = Column(String(32), nullable=True)
    train_name = Column(String(128), nullable=True)
    departure_time = Column(String(16), nullable=True)
    arrival_time = Column(String(16), nullable=True)
    journey_class = Column(String(16), default="3A")
    quota = Column(String(16), default="GN")
    
    # Passengers and financial
    passenger_count = Column(Integer, default=1)
    fare = Column(Float, nullable=True)
    payment_status = Column(String(32), default="PENDING")
    payment_upi_url = Column(Text, nullable=True)
    
    # Contact
    contact_mobile = Column(String(20), nullable=True)
    contact_email = Column(String(128), nullable=True)
    
    # Notifications
    telegram_status = Column(String(32), default="NOT_SENT")
    whatsapp_status = Column(String(32), default="NOT_SENT")
    
    # CRM & Notes
    notes = Column(Text, nullable=True)
    is_archived = Column(Boolean, default=False)
    
    # Relationships
    passengers = relationship("BookingPassenger", back_populates="booking", cascade="all, delete-orphan")

class BookingPassenger(Base):
    __tablename__ = "booking_passengers"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(128), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(8), nullable=False)
    berth_preference = Column(String(16), default="NONE")
    food_preference = Column(String(16), default="D")
    allocated_seat = Column(String(32), nullable=True)
    status = Column(String(32), default="CNF")

    booking = relationship("Booking", back_populates="passengers")

class Passenger(Base):
    __tablename__ = "passengers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(8), nullable=False)
    berth_preference = Column(String(16), default="NONE")
    food_preference = Column(String(16), default="D")
    senior_citizen = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class SavedJourney(Base):
    __tablename__ = "saved_journeys"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String(128), nullable=False)
    from_station = Column(String(64), nullable=False)
    to_station = Column(String(64), nullable=False)
    boarding_station = Column(String(64), nullable=True)
    train_preference = Column(String(64), nullable=True)
    preferred_class = Column(String(16), default="3A")
    preferred_quota = Column(String(16), default="GN")
    created_at = Column(DateTime, default=datetime.utcnow)

class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    level = Column(String(16), default="INFO")
    category = Column(String(32), default="SYSTEM")
    booking_ref = Column(String(64), nullable=True, index=True)
    message = Column(Text, nullable=False)

class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
