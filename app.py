from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from models import db, User, Mechanic, Service, Booking, mechanic_services, MechanicAvailability,Admin,FraudReport,SystemAudit,UserReport,Notification,Rating
from datetime import datetime
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from math import radians, cos, sin, asin, sqrt
from flask_socketio import SocketIO, emit, join_room
import calendar 

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mech_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

socketio = SocketIO(app, cors_allowed_origins="*")

# ------------------------
# Helper functions
# ------------------------
def haversine(lat1, lon1, lat2, lon2):
    # Calculate the great circle distance between two points on the earth (km)
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km

# --- Helper: send booking event to mechanic's Socket.IO room ---
def send_new_booking_to_mechanic(booking):
    mechanic_room = f"mechanic_{booking.mechanic_id}"
    
    socketio.emit("NEW_BOOKING", {
        "id": booking.id,
        "type": booking.type,
        "location": booking.location,
        "latitude": booking.latitude,
        "longitude": booking.longitude,
        "status": booking.status,
        "customer": {"id": booking.customer.id, "name": booking.customer.name, "phone": booking.customer.phone},
        "service": {"id": booking.service.id, "name": booking.service.name} if booking.service else None,
        "created_at": booking.created_at.isoformat() if booking.created_at else None
    }, room=mechanic_room, namespace="/")

# --- NEW HELPER: Send updated booking event to clients ---
def send_booking_update_to_client(booking):
    mechanic_room = f"mechanic_{booking.mechanic_id}"
    customer_room = f"user_{booking.customer_id}"

    booking_data = {
        "id": booking.id,
        "type": booking.type,
        "location": booking.location,
        "latitude": booking.latitude,
        "longitude": booking.longitude,
        "status": booking.status,
        "customer": {"id": booking.customer.id, "name": booking.customer.name, "phone": booking.customer.phone},
        "service": {"id": booking.service.id, "name": booking.service.name} if booking.service else None,
        "mechanic": {"id": booking.mechanic.id, "name": booking.mechanic.name, "phone": booking.mechanic.phone} if booking.mechanic else None,
        "updated_at": booking.updated_at.isoformat() if booking.updated_at else None
    }
    
    # Broadcast to mechanic's room and customer's room
    socketio.emit("BOOKING_UPDATED", booking_data, room=mechanic_room, namespace="/")
    socketio.emit("BOOKING_UPDATED", booking_data, room=customer_room, namespace="/")
    print(f"✅ BOOKING_UPDATED broadcasted for ID: {booking.id}, Status: {booking.status}")

# ------------------------
# Routes
# ------------------------



# ------------------------
# Admin Routes
# ------------------------

@app.route("/admin/register", methods=["POST"])
def create_admin():
    data = request.json
    try:
        existing_admin = Admin.query.filter_by(email=data['email']).first()
        if existing_admin:
            return jsonify({"error": "Admin with this email already exists"}), 400

        admin = Admin(
            name=data['name'],
            email=data['email'],
            password=data['password'],
            role=data.get('role', 'admin')
        )
        db.session.add(admin)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Email already exists"}), 400

    return jsonify({"message": "Admin created", "admin": {
        "id": admin.id,
        "name": admin.name,
        "email": admin.email,
        "role": admin.role,
        "status": admin.status
    }}), 201

@app.route("/admin/stats", methods=["GET"])
def get_admin_stats():
    try:
        total_users = User.query.count()
        total_mechanics = Mechanic.query.count()
        total_bookings = Booking.query.count()
        pending_bookings = Booking.query.filter_by(status='Pending').count()
        completed_bookings = Booking.query.filter_by(status='Completed').count()
        
        seven_days_ago = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        recent_bookings = Booking.query.filter(Booking.created_at >= seven_days_ago).count()
        
        return jsonify({
            "stats": {
                "total_users": total_users,
                "total_mechanics": total_mechanics,
                "total_bookings": total_bookings,
                "pending_bookings": pending_bookings,
                "completed_bookings": completed_bookings,
                "recent_bookings": recent_bookings
            }
        }), 200
    except Exception as e:
        print(f"Error getting admin stats: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/admin/users", methods=["GET"])
def get_all_users():
    try:
        users = User.query.all()
        result = []
        for user in users:
            result.append({
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "phone": user.phone,
                "status": user.status,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "bookings_count": len(user.bookings)
            })
        return jsonify(result), 200
    except Exception as e:
        print(f"Error getting users: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/admin/mechanics", methods=["GET"])
def get_all_mechanics_admin():
    try:
        mechanics = Mechanic.query.all()
        result = []
        for mechanic in mechanics:
            total_bookings = Booking.query.filter_by(mechanic_id=mechanic.id).count()
            completed_bookings = Booking.query.filter_by(mechanic_id=mechanic.id, status='Completed').count()
            
            result.append({
                "id": mechanic.id,
                "name": mechanic.name,
                "email": mechanic.email,
                "phone": mechanic.phone,
                "garage_name": mechanic.garage_name,
                "garage_location": mechanic.garage_location,
                "status": mechanic.status,
                "created_at": mechanic.created_at.isoformat() if mechanic.created_at else None,
                "total_bookings": total_bookings,
                "completed_bookings": completed_bookings,
                "services_offered": [{"id": s.id, "name": s.name} for s in mechanic.services]
            })
        return jsonify(result), 200
    except Exception as e:
        print(f"Error getting mechanics: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/admin/bookings", methods=["GET"])
def get_all_bookings_admin():
    try:
        bookings = Booking.query.options(joinedload(Booking.customer), joinedload(Booking.mechanic), joinedload(Booking.service)).order_by(Booking.created_at.desc()).all()
        
        result = []
        for booking in bookings:
            result.append({
                "id": booking.id,
                "type": booking.type,
                "location": booking.location,
                "status": booking.status,
                "created_at": booking.created_at.isoformat() if booking.created_at else None,
                "updated_at": booking.updated_at.isoformat() if booking.updated_at else None,
                "customer": {
                    "id": booking.customer.id,
                    "name": booking.customer.name,
                    "phone": booking.customer.phone
                },
                "mechanic": {
                    "id": booking.mechanic.id,
                    "name": booking.mechanic.name,
                    "phone": booking.mechanic.phone
                } if booking.mechanic else None,
                "service": {
                    "id": booking.service.id,
                    "name": booking.service.name
                } if booking.service else None
            })
        return jsonify(result), 200
    except Exception as e:
        print(f"Error getting bookings: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/admin/users/<int:user_id>/status", methods=["PUT"])
def update_user_status(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
            
        data = request.json
        new_status = data.get('status')
        if new_status not in ['active', 'inactive']:
            return jsonify({"error": "Invalid status"}), 400
            
        user.status = new_status
        db.session.commit()
        
        return jsonify({"message": f"User {new_status} successfully"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error updating user status: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/admin/mechanics/<int:mechanic_id>/status", methods=["PUT"])
def update_mechanic_status(mechanic_id):
    try:
        mechanic = Mechanic.query.get(mechanic_id)
        if not mechanic:
            return jsonify({"error": "Mechanic not found"}), 404
            
        data = request.json
        new_status = data.get('status')
        if new_status not in ['active', 'inactive']:
            return jsonify({"error": "Invalid status"}), 400
            
        mechanic.status = new_status
        db.session.commit()
        
        return jsonify({"message": f"Mechanic {new_status} successfully"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error updating mechanic status: {e}")
        return jsonify({"error": "Internal server error"}), 500

# -------- Users --------
@app.route("/register", methods=["POST"])
def create_user():
    data = request.json
    try:
        user = User(
            name=data['name'],
            email=data['email'],
            phone=data.get('phone'),
            password=data['password'],
            profile_picture=data.get('profile_picture')
        )
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Email or phone already exists"}), 400

    return jsonify({"message": "User created", "user": {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "profile_picture": user.profile_picture,
        "status": user.status
    }}), 201

@app.route("/login", methods=["POST"])
def login_user():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    # Try to find a user first
    user = User.query.filter_by(email=email).first()
    if user and user.password == password:
        return jsonify({
            "message": "Login successful",
            "role": "user",
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "phone": user.phone,
                "profile_picture": user.profile_picture,
                "status": user.status
            }
        })

    # If not a user, try mechanic
    mechanic = Mechanic.query.filter_by(email=email).first()
    if mechanic and mechanic.password == password:
        return jsonify({
            "message": "Login successful",
            "role": "mechanic",
            "mechanic": {
                "id": mechanic.id,
                "name": mechanic.name,
                "email": mechanic.email,
                "phone": mechanic.phone,
                "profile_picture": mechanic.profile_picture,
                "garage_name": mechanic.garage_name,
                "garage_location": mechanic.garage_location,
                "status": mechanic.status
            }
        })

    # ⭐ ADD THIS ADMIN CHECK SECTION ⭐
    # If not a user or mechanic, try admin
    admin = Admin.query.filter_by(email=email).first()
    if admin and admin.password == password:
        return jsonify({
            "message": "Login successful",
            "role": "admin",
            "admin": {
                "id": admin.id,
                "name": admin.name,
                "email": admin.email,
                "role": admin.role,
                "status": admin.status
            }
        })

    # If neither found
    return jsonify({"error": "Invalid credentials"}), 401



@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_data = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "profile_picture": user.profile_picture,
            "status": user.status,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "membership": "Premium Member",
            "bookings_count": len(user.bookings) if user.bookings else 0
        }
        
        return jsonify(user_data), 200
        
    except Exception as e:
        print(f"Error fetching user: {e}")
        return jsonify({"error": "Internal server error"}), 500

# -------- Services --------
@app.route("/services", methods=["GET"])
def get_services():
    services = Service.query.all()
    result = [{"id": s.id, "name": s.name} for s in services]
    return jsonify(result)

@app.route("/services", methods=["POST"])
def create_service():
    data = request.json
    service = Service(name=data['name'])
    db.session.add(service)
    db.session.commit()
    return jsonify({"message": "Service created", "service": {"id": service.id, "name": service.name}}), 201

# -------- Mechanics --------
@app.route("/mechanics", methods=["GET"])
def get_mechanics():
    mechanics = Mechanic.query.all()
    result = []
    for m in mechanics:
        result.append({
            "id": m.id,
            "name": m.name,
            "email": m.email,
            "phone": m.phone,
            "profile_picture": m.profile_picture,
            "garage_name": m.garage_name,
            "garage_location": m.garage_location,
            "latitude": m.latitude,
            "longitude": m.longitude,
            "status": m.status,
            "services_offered": [{"id": s.id, "name": s.name} for s in m.services]
        })
    return jsonify(result)

@app.route("/mechanics", methods=["POST"])
def create_mechanic():
    data = request.json
    try:
        mechanic = Mechanic(
            name=data['name'],
            email=data['email'],
            phone=data.get('phone'),
            password=data['password'],
            profile_picture=data.get('profile_picture'),
            garage_name=data.get('garage_name'),
            garage_location=data.get('garage_location'),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            document_path=data.get('document_path')
        )
        db.session.add(mechanic)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Email or phone already exists"}), 400

    # Link mechanic to existing services
    service_ids = data.get('service_ids', [])
    for sid in service_ids:
        service = Service.query.get(sid)
        if service:
            mechanic.services.append(service)
    
    # Initialize availability for the new mechanic (default all days True)
    default_availability = [
        MechanicAvailability(mechanic_id=mechanic.id, day_of_week=day, is_available=True)
        for day in calendar.day_name
    ]
    db.session.add_all(default_availability)
    
    db.session.commit()

    return jsonify({
        "message": "Mechanic created",
        "mechanic": {
            "id": mechanic.id,
            "name": mechanic.name,
            "email": mechanic.email,
            "phone": mechanic.phone,
            "profile_picture": mechanic.profile_picture,
            "garage_name": mechanic.garage_name,
            "garage_location": mechanic.garage_location,
            "latitude": mechanic.latitude,
            "longitude": mechanic.longitude,
            "services_offered": [{"id": s.id, "name": s.name} for s in mechanic.services]
        }
    }), 201

@app.route("/mechanics/<int:mechanic_id>", methods=["GET"])
def get_mechanic(mechanic_id):
    mechanic = Mechanic.query.get(mechanic_id)
    if not mechanic:
        return jsonify({"error": "Mechanic not found"}), 404

    jobs_completed = Booking.query.filter_by(
        mechanic_id=mechanic_id, 
        status="Completed"
    ).count()

    return jsonify({
        "mechanic": {
            "id": mechanic.id,
            "name": mechanic.name,
            "email": mechanic.email,
            "phone": mechanic.phone,
            "profile_picture": mechanic.profile_picture,
            "garage_name": mechanic.garage_name,
            "garage_location": mechanic.garage_location,
            "latitude": mechanic.latitude,
            "longitude": mechanic.longitude,
            "status": mechanic.status,
            "services_offered": [{"id": s.id, "name": s.name} for s in mechanic.services],
            "jobsCompleted": jobs_completed,
            "rating": 4.8, 
            "aboutShop": f"Professional auto services at {mechanic.garage_location}" if mechanic.garage_location else "Professional auto services"
        }
    })

# -------- Mechanic Availability Routes --------
@app.route("/mechanics/<int:mechanic_id>/availability", methods=["GET"])
def get_mechanic_availability(mechanic_id):
    mechanic = Mechanic.query.get(mechanic_id)
    if not mechanic:
        return jsonify({"error": "Mechanic not found"}), 404

    availability = MechanicAvailability.query.filter_by(mechanic_id=mechanic_id).all()
    
    # Map the database results to the desired frontend format
    result = {
        item.day_of_week: item.is_available
        for item in availability
    }
    
    # Ensure all days are returned, even if not explicitly set (defaults to True)
    for day in calendar.day_name:
        if day not in result:
             # Default to True if the day isn't found in the database
            result[day] = True 
            
    # Convert back to the list structure used by the frontend for consistency
    frontend_format = [
        {"day": day, "is_available": result[day]}
        for day in calendar.day_name
    ]
        
    return jsonify(frontend_format), 200

@app.route("/mechanics/<int:mechanic_id>/availability", methods=["POST"])
def set_mechanic_availability(mechanic_id):
    data = request.json
    mechanic = Mechanic.query.get(mechanic_id)
    if not mechanic:
        return jsonify({"error": "Mechanic not found"}), 404
        
    # The expected data format is a list of {"day": "Monday", "is_available": true}
    if not isinstance(data, list):
        return jsonify({"error": "Invalid data format. Expected a list of day objects."}), 400

    try:
        for day_data in data:
            day_name = day_data.get('day')
            is_available = day_data.get('is_available')

            if day_name not in calendar.day_name or is_available is None:
                continue # Skip invalid entries

            # Find or create the availability record
            availability_record = MechanicAvailability.query.filter_by(
                mechanic_id=mechanic_id, 
                day_of_week=day_name
            ).first()

            if availability_record:
                # Update existing record
                availability_record.is_available = is_available
            else:
                # Create new record
                new_record = MechanicAvailability(
                    mechanic_id=mechanic_id, 
                    day_of_week=day_name, 
                    is_available=is_available
                )
                db.session.add(new_record)
        
        db.session.commit()
        return jsonify({"message": "Availability updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error setting availability: {e}")
        return jsonify({"error": "Failed to update availability"}), 500

# -------- Bookings --------
@app.route("/bookings", methods=["POST"])
def create_booking():
    data = request.json

    # Validate required fields
    missing_fields = [f for f in ["customer_id", "service_id", "latitude", "longitude", "location"] if f not in data]
    if missing_fields:
        return jsonify({"error": f"Missing field(s): {', '.join(missing_fields)}"}), 400

    user = User.query.get(data['customer_id'])
    if not user:
        return jsonify({"error": "User not found"}), 404

    service = Service.query.get(data['service_id'])
    if not service:
        return jsonify({"error": "Service not found"}), 404
        
    # --- NEW AVAILABILITY CHECK ---
    # 1. Determine the current day of the week (e.g., 'Thursday')
    current_day = datetime.now().strftime('%A')
    
    # 2. Get all mechanics offering this service AND join their availability data
    mechanics_query = db.session.query(Mechanic).join(Mechanic.services).join(Mechanic.availability, isouter=True).filter(
        Service.id == service.id
    ).options(
        joinedload(Mechanic.availability)
    ).all()
    
    available_mechanics = []
    
    for m in mechanics_query:
        # Check if the mechanic has a specific availability record for today
        availability_record = next(
            (a for a in m.availability if a.day_of_week == current_day), 
            None
        )
        
        # Logic: If a record exists and is False, they're unavailable. 
        # Otherwise (record doesn't exist or is True), they are available by default.
        is_available = True 
        if availability_record and not availability_record.is_available:
            is_available = False
            
        if is_available and m.status == 'active': # Also ensure general status is active
            available_mechanics.append(m)

    if not available_mechanics:
        return jsonify({"error": "No mechanics available for this service at this time"}), 400

    user_lat = data['latitude']
    user_lng = data['longitude']
    
    # Find nearest mechanic from the filtered list
    nearest_mechanic = min(
        available_mechanics,
        key=lambda m: haversine(user_lat, user_lng, m.latitude, m.longitude)
    )

    # Create booking
    booking = Booking(
        type=service.name,
        location=data['location'],
        latitude=user_lat,
        longitude=user_lng,
        status="Pending",
        customer_id=user.id,
        mechanic_id=nearest_mechanic.id,
        service_id=service.id
    )
    db.session.add(booking)
    db.session.commit()

    # --- 🔔 Notify mechanic in real-time via Socket.IO ---
    send_new_booking_to_mechanic(booking)

    # Return full mechanic details
    mechanic_info = {
        "id": nearest_mechanic.id,
        "name": nearest_mechanic.name,
        "phone": nearest_mechanic.phone,
        "garage_name": nearest_mechanic.garage_name,
        "garage_location": nearest_mechanic.garage_location,
        "latitude": nearest_mechanic.latitude,
        "longitude": nearest_mechanic.longitude,
        "services_offered": [s.name for s in nearest_mechanic.services]
    }

    return jsonify({
        "message": "Booking created",
        "booking": {
            "id": booking.id,
            "type": booking.type,
            "location": booking.location,
            "status": booking.status,
            "customer": {"id": user.id, "name": user.name},
            "mechanic": mechanic_info,
            "service": {"id": service.id, "name": service.name}
        }
    }), 201

@app.route("/bookings", methods=["GET"])
def get_bookings():
    bookings = Booking.query.all()
    result = []
    for b in bookings:
        result.append({
            "id": b.id,
            "type": b.type,
            "location": b.location,
            "latitude": b.latitude,
            "longitude": b.longitude,
            "status": b.status,
            "customer": {"id": b.customer.id, "name": b.customer.name, "phone": b.customer.phone},
            "mechanic": {"id": b.mechanic.id, "name": b.mechanic.name, "phone": b.mechanic.phone} if b.mechanic else None,
            "service": {"id": b.service.id, "name": b.service.name} if b.service else None
        })
    return jsonify(result)

@app.route("/bookings/<int:booking_id>", methods=["GET"])
def get_booking(booking_id):
    booking = Booking.query.get(booking_id)
    if not booking:
        return jsonify({"error": "Booking not found"}), 404

    return jsonify({
        "id": booking.id,
        "type": booking.type,
        "location": booking.location,
        "latitude": booking.latitude,
        "longitude": booking.longitude,
        "status": booking.status,
        "customer": {
            "id": booking.customer.id,
            "name": booking.customer.name,
            "phone": booking.customer.phone
        },
        "mechanic": {
            "id": booking.mechanic.id,
            "name": booking.mechanic.name,
            "phone": booking.mechanic.phone,
            "garage_name": booking.mechanic.garage_name,
            "latitude": booking.mechanic.latitude,
            "longitude": booking.mechanic.longitude
        } if booking.mechanic else None,
        "service": {
            "id": booking.service.id,
            "name": booking.service.name
        } if booking.service else None
    })

@app.route("/bookings/<int:booking_id>/action", methods=["POST"])
def handle_booking_action(booking_id):
    data = request.json
    action = data.get("action")
    booking = Booking.query.get(booking_id)
    if not booking:
        return jsonify({"error": "Booking not found"}), 404

    if action not in ["Accepted", "Rejected", "Completed"]:
        return jsonify({"error": "Invalid action"}), 400
    
    customer = booking.customer
    mechanic = booking.mechanic

    booking.status = action
    booking.updated_at = datetime.utcnow()
    db.session.commit()
    
    send_booking_update_to_client(booking)

    return jsonify({
        "message": f"Booking {action}",
        "booking": {
            "id": booking.id,
            "type": booking.type,
            "status": booking.status,
            "customer": {"id": customer.id, "name": customer.name},
            "mechanic": {"id": mechanic.id, "name": mechanic.name} if mechanic else None,
            "service": {"id": booking.service.id, "name": booking.service.name} if booking.service else None
        }
    })

@app.route("/mechanics/<int:mechanic_id>/bookings", methods=["GET"])
def get_mechanic_bookings(mechanic_id):
    mechanic = Mechanic.query.get(mechanic_id)
    if not mechanic:
        return jsonify({"error": "Mechanic not found"}), 404

    # Eager load customer and service relations
    bookings = Booking.query.filter_by(mechanic_id=mechanic.id).options(joinedload(Booking.customer), joinedload(Booking.service)).order_by(Booking.created_at.desc()).all()
    
    result = []
    for b in bookings:
        # NOTE: Ensure you are returning latitude/longitude for the customer pickup
        result.append({
            "id": b.id,
            "type": b.type,
            "location": b.location,
            "latitude": b.latitude, # Customer request lat
            "longitude": b.longitude, # Customer request lng
            "status": b.status,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "customer": {
                "id": b.customer.id,
                "name": b.customer.name,
                "phone": b.customer.phone
            },
            "service": {
                "id": b.service.id,
                "name": b.service.name
            } if b.service else None
        })
    return jsonify(result)

@app.route("/users/<int:user_id>/bookings", methods=["GET"])
def get_user_bookings(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    bookings = Booking.query.filter_by(customer_id=user.id).options(
        joinedload(Booking.mechanic), 
        joinedload(Booking.service)
    ).order_by(Booking.created_at.desc()).all()
    
    result = []
    for b in bookings:
        result.append({
            "id": b.id,
            "type": b.type,
            "location": b.location,
            "latitude": b.latitude,
            "longitude": b.longitude,
            "status": b.status,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "mechanic": {
                "id": b.mechanic.id,
                "name": b.mechanic.name,
                "phone": b.mechanic.phone,
                "garage_name": b.mechanic.garage_name
            } if b.mechanic else None,
            "service": {
                "id": b.service.id,
                "name": b.service.name
            } if b.service else None
        })
    return jsonify(result)

# -------- Socket.IO Events --------
@socketio.on("join")
def on_join(data):
    mechanic_id = data.get("mechanic_id")
    user_id = data.get("user_id") 
    if mechanic_id:
        join_room(f"mechanic_{mechanic_id}")
        emit("message", {"info": f"Mechanic {mechanic_id} joined room"}, room=f"mechanic_{mechanic_id}")
    elif user_id:
        join_room(f"user_{user_id}")
        emit("message", {"info": f"User {user_id} joined room"}, room=f"user_{user_id}")


def create_default_admin():
    """Create a default super admin if none exists"""
    with app.app_context():
        existing_admin = Admin.query.filter_by(email='admin@mechapp.com').first()
        if not existing_admin:
            super_admin = Admin(
                name='Super Admin',
                email='admin@mechapp.com',
                password='admin123',
                role='super_admin'
            )
            db.session.add(super_admin)
            db.session.commit()
            print("✅ Default super admin created: admin@mechapp.com / admin123")


# ------------------------
# Enhanced Admin Reports Routes
# ------------------------

@app.route("/admin/reports/stats", methods=["GET"])
def get_admin_reports_stats():  # ⭐ CHANGED NAME
    """Get comprehensive dashboard statistics for admin"""
    try:
        total_users = User.query.count()
        total_mechanics = Mechanic.query.count()
        total_bookings = Booking.query.count()
        pending_bookings = Booking.query.filter_by(status='Pending').count()
        active_bookings = Booking.query.filter(Booking.status.in_(['Pending', 'Accepted'])).count()
        completed_bookings = Booking.query.filter_by(status='Completed').count()
        cancelled_bookings = Booking.query.filter_by(status='Rejected').count()
        
        # Recent activity (last 7 days)
        from datetime import timedelta
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_users = User.query.filter(User.created_at >= seven_days_ago).count()
        recent_mechanics = Mechanic.query.filter(Mechanic.created_at >= seven_days_ago).count()
        recent_bookings = Booking.query.filter(Booking.created_at >= seven_days_ago).count()
        
        # Fraud reports stats (with safe check)
        try:
            pending_fraud_reports = FraudReport.query.filter_by(status='pending').count()
            total_fraud_reports = FraudReport.query.count()
        except:
            pending_fraud_reports = 0
            total_fraud_reports = 0
        
        return jsonify({
            "stats": {
                "total_users": total_users,
                "total_mechanics": total_mechanics,
                "total_bookings": total_bookings,
                "active_bookings": active_bookings,
                "pending_bookings": pending_bookings,
                "completed_bookings": completed_bookings,
                "cancelled_bookings": cancelled_bookings,
                "recent_users": recent_users,
                "recent_mechanics": recent_mechanics,
                "recent_bookings": recent_bookings,
                "pending_fraud_reports": pending_fraud_reports,
                "total_fraud_reports": total_fraud_reports,
            }
        }), 200
    except Exception as e:
        print(f"Error getting admin stats: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/admin/reports/fraud-reports", methods=["GET"])
def get_fraud_reports():
    """Get all fraud reports with detailed information"""
    try:
        fraud_reports = FraudReport.query.options(
            joinedload(FraudReport.user),
            joinedload(FraudReport.mechanic),
            joinedload(FraudReport.booking),
            joinedload(FraudReport.resolver)
        ).order_by(FraudReport.created_at.desc()).all()
        
        result = []
        for report in fraud_reports:
            result.append({
                "id": report.id,
                "user": {
                    "id": report.user.id,
                    "name": report.user.name,
                    "email": report.user.email,
                    "phone": report.user.phone
                },
                "mechanic": {
                    "id": report.mechanic.id,
                    "name": report.mechanic.name,
                    "email": report.mechanic.email,
                    "garage_name": report.mechanic.garage_name
                },
                "booking": {
                    "id": report.booking.id,
                    "type": report.booking.type,
                    "status": report.booking.status
                } if report.booking else None,
                "reason": report.reason,
                "description": report.description,
                "status": report.status,
                "severity": report.severity,
                "evidence_images": report.evidence_images,
                "created_at": report.created_at.isoformat(),
                "updated_at": report.updated_at.isoformat() if report.updated_at else None,
                "resolved_at": report.resolved_at.isoformat() if report.resolved_at else None,
                "resolver": report.resolver.name if report.resolver else None,
                "resolution_notes": report.resolution_notes
            })
        
        return jsonify(result), 200
    except Exception as e:
        print(f"Error getting fraud reports: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/admin/reports/fraud-reports/<int:report_id>", methods=["GET"])
def get_fraud_report_detail(report_id):
    """Get detailed information about a specific fraud report"""
    try:
        report = FraudReport.query.options(
            joinedload(FraudReport.user),
            joinedload(FraudReport.mechanic),
            joinedload(FraudReport.booking),
            joinedload(FraudReport.resolver)
        ).filter_by(id=report_id).first()
        
        if not report:
            return jsonify({"error": "Fraud report not found"}), 404
            
        return jsonify({
            "id": report.id,
            "user": {
                "id": report.user.id,
                "name": report.user.name,
                "email": report.user.email,
                "phone": report.user.phone,
                "created_at": report.user.created_at.isoformat()
            },
            "mechanic": {
                "id": report.mechanic.id,
                "name": report.mechanic.name,
                "email": report.mechanic.email,
                "garage_name": report.mechanic.garage_name,
                "garage_location": report.mechanic.garage_location,
                "status": report.mechanic.status,
                "created_at": report.mechanic.created_at.isoformat()
            },
            "booking": {
                "id": report.booking.id,
                "type": report.booking.type,
                "location": report.booking.location,
                "status": report.booking.status,
                "created_at": report.booking.created_at.isoformat()
            } if report.booking else None,
            "reason": report.reason,
            "description": report.description,
            "status": report.status,
            "severity": report.severity,
            "evidence_images": report.evidence_images,
            "created_at": report.created_at.isoformat(),
            "updated_at": report.updated_at.isoformat() if report.updated_at else None,
            "resolved_at": report.resolved_at.isoformat() if report.resolved_at else None,
            "resolver": report.resolver.name if report.resolver else None,
            "resolution_notes": report.resolution_notes
        }), 200
    except Exception as e:
        print(f"Error getting fraud report detail: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/admin/reports/fraud-reports/<int:report_id>/resolve", methods=["PUT"])
def resolve_fraud_report(report_id):
    """Resolve a fraud report (block mechanic, dismiss, etc.)"""
    try:
        data = request.json
        action = data.get("action")  # block_mechanic, dismiss, warn
        resolution_notes = data.get("resolution_notes", "")
        admin_id = data.get("admin_id")  # ID of admin resolving the report
        
        report = FraudReport.query.get(report_id)
        if not report:
            return jsonify({"error": "Fraud report not found"}), 404
            
        admin = Admin.query.get(admin_id)
        if not admin:
            return jsonify({"error": "Admin not found"}), 404
            
        if action == "block_mechanic":
            # Block the mechanic
            mechanic = Mechanic.query.get(report.mechanic_id)
            if mechanic:
                mechanic.status = "inactive"
                
            report.status = "resolved"
            report.resolution_notes = f"Mechanic blocked. {resolution_notes}"
            
        elif action == "dismiss":
            report.status = "dismissed"
            report.resolution_notes = f"Report dismissed. {resolution_notes}"
            
        elif action == "warn":
            report.status = "resolved"
            report.resolution_notes = f"Warning issued. {resolution_notes}"
            # Here you could add logic to send a warning to the mechanic
            
        else:
            return jsonify({"error": "Invalid action"}), 400
            
        report.resolved_at = datetime.utcnow()
        report.resolved_by = admin_id
        report.updated_at = datetime.utcnow()
        
        # Create audit log
        audit = SystemAudit(
            admin_id=admin_id,
            action=f"fraud_report_{action}",
            target_type="fraud_report",
            target_id=report_id,
            description=f"Resolved fraud report #{report_id} with action: {action}"
        )
        db.session.add(audit)
        
        db.session.commit()
        
        return jsonify({
            "message": f"Fraud report {action} successfully",
            "report": {
                "id": report.id,
                "status": report.status,
                "resolved_at": report.resolved_at.isoformat()
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error resolving fraud report: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/admin/reports/user-reports", methods=["GET"])
def get_user_reports():
    """Get reports made by users against other users"""
    try:
        user_reports = UserReport.query.options(
            joinedload(UserReport.reporter),
            joinedload(UserReport.reported_user)
        ).order_by(UserReport.created_at.desc()).all()
        
        result = []
        for report in user_reports:
            result.append({
                "id": report.id,
                "reporter": {
                    "id": report.reporter.id,
                    "name": report.reporter.name,
                    "email": report.reporter.email
                },
                "reported_user": {
                    "id": report.reported_user.id,
                    "name": report.reported_user.name,
                    "email": report.reported_user.email
                },
                "report_type": report.report_type,
                "description": report.description,
                "status": report.status,
                "created_at": report.created_at.isoformat()
            })
        
        return jsonify(result), 200
    except Exception as e:
        print(f"Error getting user reports: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/admin/audit-logs", methods=["GET"])
def get_audit_logs():
    """Get system audit logs for admin activity tracking"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        audit_logs = SystemAudit.query.options(
            joinedload(SystemAudit.admin)
        ).order_by(SystemAudit.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        result = []
        for log in audit_logs.items:
            result.append({
                "id": log.id,
                "admin": log.admin.name if log.admin else "System",
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "description": log.description,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "created_at": log.created_at.isoformat()
            })
        
        return jsonify({
            "logs": result,
            "total": audit_logs.total,
            "pages": audit_logs.pages,
            "current_page": page
        }), 200
    except Exception as e:
        print(f"Error getting audit logs: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/reports/fraud", methods=["POST"])
def create_fraud_report():
    """Endpoint for users to report fraud"""
    try:
        data = request.json
        user_id = data.get('user_id')
        mechanic_id = data.get('mechanic_id')
        booking_id = data.get('booking_id')
        reason = data.get('reason')
        description = data.get('description', '')
        
        # Validate required fields
        if not all([user_id, mechanic_id, reason]):
            return jsonify({"error": "Missing required fields"}), 400
            
        # Check if user and mechanic exist
        user = User.query.get(user_id)
        mechanic = Mechanic.query.get(mechanic_id)
        if not user or not mechanic:
            return jsonify({"error": "User or mechanic not found"}), 404
            
        # Create fraud report
        fraud_report = FraudReport(
            user_id=user_id,
            mechanic_id=mechanic_id,
            booking_id=booking_id,
            reason=reason,
            description=description,
            status='pending'
        )
        
        db.session.add(fraud_report)
        db.session.commit()
        
        # Create notification for admins (you can implement this later)
        # notify_admins_about_fraud_report(fraud_report)
        
        return jsonify({
            "message": "Fraud report submitted successfully",
            "report_id": fraud_report.id
        }), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error creating fraud report: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ------------------------
# Notification Routes
# ------------------------

@app.route("/admin/notifications", methods=["GET"])
def get_admin_notifications():
    """Get notifications for admin"""
    try:
        notifications = Notification.query.filter_by(admin_id=None).order_by(Notification.created_at.desc()).limit(50).all()
        
        result = []
        for notification in notifications:
            result.append({
                "id": notification.id,
                "title": notification.title,
                "message": notification.message,
                "type": notification.type,
                "is_read": notification.is_read,
                "related_entity": notification.related_entity,
                "related_entity_id": notification.related_entity_id,
                "created_at": notification.created_at.isoformat()
            })
        
        return jsonify(result), 200
    except Exception as e:
        print(f"Error getting notifications: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/admin/notifications/<int:notification_id>/read", methods=["PUT"])
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    try:
        notification = Notification.query.get(notification_id)
        if not notification:
            return jsonify({"error": "Notification not found"}), 404
            
        notification.is_read = True
        db.session.commit()
        
        return jsonify({"message": "Notification marked as read"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error marking notification as read: {e}")
        return jsonify({"error": "Internal server error"}), 500
    
    
# Add these routes to your app.py (using your existing FraudReport table)

@app.route("/ratings", methods=["POST"])
def create_rating():
    """Create a rating for a completed booking"""
    try:
        data = request.json
        booking_id = data.get('booking_id')
        user_id = data.get('user_id')
        rating_value = data.get('rating')
        comment = data.get('comment', '')

        # Validate required fields
        if not all([booking_id, user_id, rating_value]):
            return jsonify({"error": "Missing required fields"}), 400

        # Check if booking exists and is completed
        booking = Booking.query.get(booking_id)
        if not booking:
            return jsonify({"error": "Booking not found"}), 404
        
        if booking.status != 'Completed':
            return jsonify({"error": "Can only rate completed bookings"}), 400

        # Check if user has already rated this booking
        existing_rating = Rating.query.filter_by(booking_id=booking_id, user_id=user_id).first()
        if existing_rating:
            return jsonify({"error": "You have already rated this booking"}), 400

        # Validate rating value
        if rating_value < 1 or rating_value > 5:
            return jsonify({"error": "Rating must be between 1 and 5"}), 400

        # Create rating
        rating = Rating(
            booking_id=booking_id,
            user_id=user_id,
            mechanic_id=booking.mechanic_id,
            rating=rating_value,
            comment=comment
        )
        
        db.session.add(rating)
        
        # Create notification for mechanic
        notification = Notification(
            mechanic_id=booking.mechanic_id,
            title="New Rating Received",
            message=f"You received a {rating_value}-star rating from {booking.customer.name}",
            type="info",
            related_entity="rating",
            related_entity_id=rating.id
        )
        db.session.add(notification)
        
        db.session.commit()

        return jsonify({
            "message": "Rating submitted successfully",
            "rating": {
                "id": rating.id,
                "rating": rating.rating,
                "comment": rating.comment,
                "created_at": rating.created_at.isoformat()
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error creating rating: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/complaints/fraud", methods=["POST"])
def create_fraud_complaint():
    """Create a fraud complaint using existing FraudReport table"""
    try:
        data = request.json
        user_id = data.get('user_id')
        mechanic_id = data.get('mechanic_id')
        booking_id = data.get('booking_id')
        complaint_type = data.get('complaint_type')
        description = data.get('description')

        # Validate required fields
        if not all([user_id, mechanic_id, booking_id, complaint_type, description]):
            return jsonify({"error": "Missing required fields"}), 400

        # Create complaint using existing FraudReport table
        complaint = FraudReport(
            user_id=user_id,
            mechanic_id=mechanic_id,
            booking_id=booking_id,
            reason=complaint_type,  # Using 'reason' field for complaint_type
            description=description,
            status='pending',
            severity='medium'
        )
        
        db.session.add(complaint)
        
        # Create notification for admin
        user = User.query.get(user_id)
        mechanic = Mechanic.query.get(mechanic_id)
        
        notification = Notification(
            admin_id=1,  # Notify first admin or you can query for active admins
            title="New Fraud Report",
            message=f"Fraud report submitted by {user.name} against {mechanic.name}",
            type="alert",
            related_entity="fraud_report",
            related_entity_id=complaint.id
        )
        db.session.add(notification)
        
        # Create audit log
        audit = SystemAudit(
            admin_id=None,  # System-generated
            action="fraud_report_submitted",
            target_type="fraud_report",
            target_id=complaint.id,
            description=f"User {user_id} submitted fraud report against mechanic {mechanic_id}"
        )
        db.session.add(audit)
        
        db.session.commit()

        return jsonify({
            "message": "Complaint submitted successfully",
            "complaint_id": complaint.id
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error creating complaint: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/bookings/<int:booking_id>/rating", methods=["GET"])
def get_booking_rating(booking_id):
    """Get rating for a specific booking"""
    try:
        rating = Rating.query.filter_by(booking_id=booking_id).first()
        
        if not rating:
            return jsonify({"rating": None}), 200
            
        return jsonify({
            "rating": {
                "id": rating.id,
                "rating": rating.rating,
                "comment": rating.comment,
                "created_at": rating.created_at.isoformat()
            }
        }), 200

    except Exception as e:
        print(f"Error getting rating: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/mechanics/<int:mechanic_id>/average-rating", methods=["GET"])
def get_mechanic_average_rating(mechanic_id):
    """Get average rating for a mechanic"""
    try:
        ratings = Rating.query.filter_by(mechanic_id=mechanic_id).all()
        
        if not ratings:
            return jsonify({
                "average_rating": 0,
                "total_ratings": 0,
                "rating_breakdown": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            }), 200
        
        total_ratings = len(ratings)
        average_rating = sum(r.rating for r in ratings) / total_ratings
        
        # Calculate rating breakdown
        breakdown = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for rating in ratings:
            breakdown[rating.rating] += 1
        
        return jsonify({
            "average_rating": round(average_rating, 1),
            "total_ratings": total_ratings,
            "rating_breakdown": breakdown
        }), 200

    except Exception as e:
        print(f"Error getting mechanic rating: {e}")
        return jsonify({"error": "Internal server error"}), 500
    
    
# ------------------------
# Initialize database
# ------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_default_admin()  # Add this line
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)