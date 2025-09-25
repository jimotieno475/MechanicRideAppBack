from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    profile_picture = db.Column(db.String(200), nullable=True)
    password = db.Column(db.String(200), nullable=False)  # ⚠️ hash in production
    status = db.Column(db.String(20), default="active")  # active, blocked
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to bookings
    bookings = db.relationship("Booking", back_populates="customer", foreign_keys="Booking.customer_id")

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
    latitude = db.Column(db.Float, nullable=True)   # For nearest mechanic calculation
    longitude = db.Column(db.Float, nullable=True)  # For nearest mechanic calculation
    status = db.Column(db.String(20), default="active")  # active, blocked
    document_path = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to bookings
    bookings = db.relationship("Booking", back_populates="mechanic", foreign_keys="Booking.mechanic_id")

    # Relationship to services
    services = db.relationship("Service", secondary="mechanic_services", back_populates="mechanics")

    def __repr__(self):
        return f"<Mechanic {self.name}>"


class Service(db.Model):
    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default="Available")  # e.g., Emergency, Can Drive
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to mechanics
    mechanics = db.relationship("Mechanic", secondary="mechanic_services", back_populates="services")

    def __repr__(self):
        return f"<Service {self.name}>"


# Association table for many-to-many between Mechanics and Services
mechanic_services = db.Table(
    "mechanic_services",
    db.Column("mechanic_id", db.Integer, db.ForeignKey("mechanics.id"), primary_key=True),
    db.Column("service_id", db.Integer, db.ForeignKey("services.id"), primary_key=True)
)


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default="Pending")  # Pending, Accepted, Rejected, Completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Foreign Keys
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    mechanic_id = db.Column(db.Integer, db.ForeignKey("mechanics.id"), nullable=True)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=True)  # Optional: link to Service

    # Relationships
    customer = db.relationship("User", back_populates="bookings", foreign_keys=[customer_id])
    mechanic = db.relationship("Mechanic", back_populates="bookings", foreign_keys=[mechanic_id])
    service = db.relationship("Service")
    


    def __repr__(self):
        return f"<Booking {self.type} - {self.status}>"
