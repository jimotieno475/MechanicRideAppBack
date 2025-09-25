from app import db, app
from models import User, Mechanic, Service, Booking, MechanicAvailability
from datetime import datetime
import calendar

# -----------------------
# Seed Data
# -----------------------

predefined_services = [
    "Oil Change",
    "Brake Repair",
    "Tire Replacement",
    "Engine Diagnostics",
    "Battery Replacement",
    "Transmission Repair",
    "Suspension Repair",
    "Air Conditioning",
    "Electrical Systems",
    "Car Wash & Detailing"
]

with app.app_context():
    # Reset database
    db.drop_all()
    db.create_all()

    # -----------------------
    # Create services
    # -----------------------
    services = []
    for name in predefined_services:
        service = Service(name=name)
        db.session.add(service)
        services.append(service)
    db.session.commit()

    # -----------------------
    # Create users
    # -----------------------
    user1 = User(
        name="Alice Johnson",
        email="alice@example.com",
        phone="+254700111222",
        password="password123"
    )
    user2 = User(
        name="Bob Williams",
        email="bob@example.com",
        phone="+254700333444",
        password="password123"
    )
    db.session.add_all([user1, user2])
    db.session.commit()

    # -----------------------
    # Create mechanics
    # -----------------------
    mech1 = Mechanic(
        name="Joe Garage",
        email="joe@example.com",
        phone="+254701234567",
        password="password123",
        garage_name="Joe's Garage",
        garage_location="123 Main St, Nairobi",
        latitude=-1.28333,
        longitude=36.81667
    )

    mech2 = Mechanic(
        name="QuickFix Auto",
        email="quickfix@example.com",
        phone="+254712345678",
        password="password123",
        garage_name="QuickFix Garage",
        garage_location="456 Park Ave, Nairobi",
        latitude=-1.2900,
        longitude=36.8200
    )

    db.session.add_all([mech1, mech2])
    db.session.commit()

    # -----------------------
    # Assign services to mechanics
    # -----------------------
    mech1.services.extend(services[:5])   # Joe Garage offers first 5 services
    mech2.services.extend(services[5:])   # QuickFix Auto offers last 5 services
    db.session.commit()
    
    # -----------------------
    # Seed mechanic availability (necessary for new booking logic)
    # -----------------------
    print("\nSeeding default availability for all mechanics...")
    # Get all days of the week
    all_days = list(calendar.day_name)
    
    # Create a list to hold all new availability records
    availability_records = []
    
    # Iterate through each mechanic and each day to create a record
    for mechanic in Mechanic.query.all():
        for day in all_days:
            # By default, a mechanic is available every day
            record = MechanicAvailability(
                mechanic_id=mechanic.id,
                day_of_week=day,
                is_available=True
            )
            availability_records.append(record)
            
    db.session.add_all(availability_records)
    db.session.commit()
    print("✅ Availability seeded successfully.")

    # -----------------------
    # Create sample bookings
    # -----------------------
    booking1 = Booking(
        type=services[0].name,
        location="123 User St, Nairobi",
        latitude=-1.2850,
        longitude=36.8170,
        status="Pending",
        customer_id=user1.id,
        mechanic_id=mech1.id,
        service_id=services[0].id
    )

    booking2 = Booking(
        type=services[6].name,
        location="456 User Rd, Nairobi",
        latitude=-1.2870,
        longitude=36.8190,
        status="Pending",
        customer_id=user2.id,
        mechanic_id=mech2.id,
        service_id=services[6].id
    )

    db.session.add_all([booking1, booking2])
    db.session.commit()

    # -----------------------
    # Print out mechanics and their services
    # -----------------------
    print("\n✅ Mechanics and their services:")
    for mech in Mechanic.query.all():
        service_names = [s.name for s in mech.services]
        print(f"{mech.name} offers: {service_names}")

    # -----------------------
    # Print out bookings with mechanic and service info
    # -----------------------
    print("\n✅ Bookings with details:")
    for b in Booking.query.all():
        print({
            "booking_id": b.id,
            "customer": b.customer.name,
            "mechanic": b.mechanic.name if b.mechanic else None,
            "service": b.service.name if b.service else None,
            "status": b.status,
            "location": b.location
        })