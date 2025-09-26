# File: models.py

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    profile_picture = db.Column(db.Text, nullable=True)  # Changed to Text for larger base64 strings
    password = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default="active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bookings = db.relationship("Booking", back_populates="customer", foreign_keys="Booking.customer_id")

    def to_dict(self):
        """Convert user object to dictionary for JSON response"""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "profile_picture": self.profile_picture,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "membership": "Premium Member",  # You can make this dynamic later
            "bookings_count": len(self.bookings) if self.bookings else 0
        }

    def __repr__(self):
        return f"<User {self.name}>"

class Mechanic(db.Model):
    __tablename__ = "mechanics"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    password = db.Column(db.String(200), nullable=False)
    profile_picture = db.Column(db.String(200), nullable=True)

    garage_name = db.Column(db.String(150), nullable=True)
    garage_location = db.Column(db.String(200), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default="active") # active, blocked
    document_path = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bookings = db.relationship("Booking", back_populates="mechanic", foreign_keys="Booking.mechanic_id")
    services = db.relationship("Service", secondary="mechanic_services", back_populates="mechanics")
    
    # NEW: Relationship to availability schedule
    availability = db.relationship("MechanicAvailability", back_populates="mechanic", cascade="all, delete-orphan")


    def __repr__(self):
        return f"<Mechanic {self.name}>"


# Association table for many-to-many between Mechanics and Services
mechanic_services = db.Table(
    "mechanic_services",
    db.Column("mechanic_id", db.Integer, db.ForeignKey("mechanics.id"), primary_key=True),
    db.Column("service_id", db.Integer, db.ForeignKey("services.id"), primary_key=True)
)

#admin model
class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='admin')  # admin, super_admin
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# NEW MODEL: MechanicAvailability
class MechanicAvailability(db.Model):
    __tablename__ = "mechanic_availability"

    id = db.Column(db.Integer, primary_key=True)
    mechanic_id = db.Column(db.Integer, db.ForeignKey("mechanics.id"), nullable=False)
    
    # Day of the week (0=Monday, 6=Sunday based on Python's weekday() or 1-7 for simplicity)
    # Storing as string (e.g., 'Monday', 'Tuesday') is often simplest for UI/DB sync
    day_of_week = db.Column(db.String(10), nullable=False) 
    
    # True if available, False if unavailable
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    
    # Constraint to ensure a mechanic only has one entry per day
    __table_args__ = (db.UniqueConstraint('mechanic_id', 'day_of_week', name='_mechanic_day_uc'),)

    mechanic = db.relationship("Mechanic", back_populates="availability")

    def __repr__(self):
        return f"<Availability Mechanic:{self.mechanic_id} Day:{self.day_of_week} Available:{self.is_available}>"


class Service(db.Model):
    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default="Available")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    mechanics = db.relationship("Mechanic", secondary="mechanic_services", back_populates="services")

    def __repr__(self):
        return f"<Service {self.name}>"


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    mechanic_id = db.Column(db.Integer, db.ForeignKey("mechanics.id"), nullable=True)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=True)

    customer = db.relationship("User", back_populates="bookings", foreign_keys=[customer_id])
    mechanic = db.relationship("Mechanic", back_populates="bookings", foreign_keys=[mechanic_id])
    service = db.relationship("Service")

    def __repr__(self):
        return f"<Booking {self.type} - {self.status}>"
    
    
# Add these new models to your existing models.py

class FraudReport(db.Model):
    __tablename__ = 'fraud_reports'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    mechanic_id = db.Column(db.Integer, db.ForeignKey('mechanics.id'), nullable=False)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=True)
    reason = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)  # Detailed description
    status = db.Column(db.String(20), default='pending')  # pending, under_review, resolved, dismissed
    severity = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    evidence_images = db.Column(db.Text)  # JSON string of image URLs
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=True)
    resolution_notes = db.Column(db.Text)

    # Relationships
    user = db.relationship('User', backref='fraud_reports_filed')
    mechanic = db.relationship('Mechanic', backref='fraud_reports_against')
    booking = db.relationship('Booking', backref='fraud_reports')
    resolver = db.relationship('Admin', foreign_keys=[resolved_by])

class UserReport(db.Model):
    __tablename__ = 'user_reports'
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reported_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    report_type = db.Column(db.String(50), nullable=False)  # spam, harassment, fake_profile, etc.
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    reporter = db.relationship('User', foreign_keys=[reporter_id], backref='reports_made')
    reported_user = db.relationship('User', foreign_keys=[reported_user_id], backref='reports_against')

class SystemAudit(db.Model):
    __tablename__ = 'system_audits'
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)  # user_blocked, mechanic_blocked, etc.
    target_type = db.Column(db.String(50))  # user, mechanic, booking
    target_id = db.Column(db.Integer)  # ID of the target
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    admin = db.relationship('Admin', backref='audit_logs')

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    mechanic_id = db.Column(db.Integer, db.ForeignKey('mechanics.id'), nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), default='info')  # info, warning, alert, success
    is_read = db.Column(db.Boolean, default=False)
    related_entity = db.Column(db.String(50))  # booking, report, user, mechanic
    related_entity_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='notifications')
    mechanic = db.relationship('Mechanic', backref='notifications')
    admin = db.relationship('Admin', backref='notifications')
    
# Add this ONE table to your existing models.py

class Rating(db.Model):
    __tablename__ = 'ratings'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    mechanic_id = db.Column(db.Integer, db.ForeignKey('mechanics.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    booking = db.relationship('Booking', backref='ratings')
    user = db.relationship('User', backref='ratings_given')
    mechanic = db.relationship('Mechanic', backref='ratings_received')

    def __repr__(self):
        return f"<Rating {self.rating} stars for Booking {self.booking_id}>"