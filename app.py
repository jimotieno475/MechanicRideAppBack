# File: app.py

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from models import db, User, Mechanic, Service, Booking, mechanic_services
from datetime import datetime
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from math import radians, cos, sin, asin, sqrt
from flask_socketio import SocketIO, emit, join_room


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


# ------------------------
# Routes
# ------------------------

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

    # If neither found
    return jsonify({"error": "Invalid credentials"}), 401


# -------- Mechanics --------
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


# -------- Services --------
@app.route("/services", methods=["GET"])
def get_services():
    services = Service.query.options(joinedload(Service.mechanics)).all()
    result = []
    for s in services:
        result.append({
            "id": s.id,
            "name": s.name,
            "status": s.status,
            "mechanics": [
                {
                    "id": m.id,
                    "name": m.name,
                    "latitude": m.latitude,
                    "longitude": m.longitude,
                    "phone": m.phone,
                    "garage_location": m.garage_location
                }
                for m in s.mechanics
            ]
        })
    return jsonify(result)


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

    # Find nearest mechanic offering this service
    mechanics = service.mechanics
    if not mechanics:
        return jsonify({"error": "No mechanics available for this service"}), 400

    user_lat = data['latitude']
    user_lng = data['longitude']
    nearest_mechanic = min(
        mechanics,
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


# --- Helper: send booking event to mechanic's Socket.IO room ---
def send_new_booking_to_mechanic(booking):
    mechanic_room = f"mechanic_{booking.mechanic_id}"
    
    # Use socketio.emit() instead of emit() for server-side broadcasting
    socketio.emit("NEW_BOOKING", {
        "id": booking.id,
        "type": booking.type,
        "location": booking.location,
        "status": booking.status,
        "customer": {"id": booking.customer.id, "name": booking.customer.name},
        "created_at": booking.created_at.isoformat() if booking.created_at else None
    }, room=mechanic_room, namespace="/")

@app.route("/bookings/<int:booking_id>/action", methods=["POST"])
def handle_booking_action(booking_id):
    data = request.json
    action = data.get("action")  # Accepted, Rejected, Completed
    booking = Booking.query.get(booking_id)
    if not booking:
        return jsonify({"error": "Booking not found"}), 404

    if action not in ["Accepted", "Rejected", "Completed"]:
        return jsonify({"error": "Invalid action"}), 400

    booking.status = action
    booking.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "message": f"Booking {action}",
        "booking": {
            "id": booking.id,
            "type": booking.type,
            "status": booking.status,
            "customer": {"id": booking.customer.id, "name": booking.customer.name},
            "mechanic": {"id": booking.mechanic.id, "name": booking.mechanic.name} if booking.mechanic else None,
            "service": {"id": booking.service.id, "name": booking.service.name} if booking.service else None
        }
    })


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


@app.route("/mechanics/<int:mechanic_id>/bookings", methods=["GET"])
def get_mechanic_bookings(mechanic_id):
    mechanic = Mechanic.query.get(mechanic_id)
    if not mechanic:
        return jsonify({"error": "Mechanic not found"}), 404

    bookings = Booking.query.filter_by(mechanic_id=mechanic.id).all()
    result = []
    for b in bookings:
        result.append({
            "id": b.id,
            "type": b.type,
            "location": b.location,
            "latitude": b.latitude,
            "longitude": b.longitude,
            "status": b.status,
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


@socketio.on("join")
def on_join(data):
    mechanic_id = data.get("mechanic_id")
    if mechanic_id:
        join_room(f"mechanic_{mechanic_id}")
        emit("message", {"info": f"Mechanic {mechanic_id} joined room"}, room=f"mechanic_{mechanic_id}")


@app.route("/mechanics/<int:mechanic_id>", methods=["GET"])
def get_mechanic(mechanic_id):
    mechanic = Mechanic.query.get(mechanic_id)
    if not mechanic:
        return jsonify({"error": "Mechanic not found"}), 404

    # Calculate jobs completed (you might need to adjust based on your Booking model)
    from models import Booking  # Import if needed
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
            "rating": 4.8,  # Placeholder - implement rating calculation later
            "aboutShop": f"Professional auto services at {mechanic.garage_location}" if mechanic.garage_location else "Professional auto services"
        }
    })
    

@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Return user data (excluding password for security)
        user_data = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "profile_picture": user.profile_picture,
            "status": user.status,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "membership": "Premium Member",  # You can add membership logic later
            "bookings_count": len(user.bookings) if user.bookings else 0
        }
        
        return jsonify(user_data), 200
        
    except Exception as e:
        print(f"Error fetching user: {e}")
        return jsonify({"error": "Internal server error"}), 500
# ------------------------
# Initialize database
# ------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
