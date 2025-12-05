"""
PharmaCheck Authentication Module
Handles user registration, login, JWT token management
"""

import jwt
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, g

from config import config
from database import Session, User


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def generate_token(user_id: int, role: str) -> str:
    """Generate a JWT token for authenticated user"""
    payload = {
        'user_id': user_id,
        'role': role,
        'exp': datetime.utcnow() + config.JWT_ACCESS_TOKEN_EXPIRES,
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token"""
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_current_user():
    """Get the current authenticated user from the request"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    payload = decode_token(token)
    
    if not payload:
        return None
    
    session = Session()
    try:
        user = session.query(User).filter(User.user_id == payload['user_id']).first()
        return user
    finally:
        session.close()


def login_required(f):
    """Decorator to require authentication for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        g.current_user = user
        return f(*args, **kwargs)
    return decorated_function


def role_required(role: str):
    """Decorator to require a specific role for a route"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({'error': 'Authentication required'}), 401
            if user.role != role:
                return jsonify({'error': f'{role} role required'}), 403
            g.current_user = user
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def register_user(username: str, email: str, password: str, role: str = 'PATIENT') -> dict:
    """Register a new user"""
    session = Session()
    try:
        # Check if username already exists
        existing_user = session.query(User).filter(User.username == username).first()
        if existing_user:
            return {'success': False, 'error': 'Username already exists'}
        
        # Check if email already exists
        existing_email = session.query(User).filter(User.email == email).first()
        if existing_email:
            return {'success': False, 'error': 'Email already registered'}
        
        # Validate role
        if role not in ['PATIENT', 'DOCTOR']:
            return {'success': False, 'error': 'Invalid role. Must be PATIENT or DOCTOR'}
        
        # Create new user
        password_hash = hash_password(password)
        new_user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role
        )
        
        session.add(new_user)
        session.commit()
        
        # Generate token
        token = generate_token(new_user.user_id, new_user.role)
        
        return {
            'success': True,
            'user': new_user.to_dict(),
            'token': token
        }
    except Exception as e:
        session.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        session.close()


def login_user(username: str, password: str) -> dict:
    """Authenticate user and return token"""
    session = Session()
    try:
        # Find user by username or email
        user = session.query(User).filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if not user:
            return {'success': False, 'error': 'Invalid username or password'}
        
        # Verify password
        if not verify_password(password, user.password_hash):
            return {'success': False, 'error': 'Invalid username or password'}
        
        # Generate token
        token = generate_token(user.user_id, user.role)
        
        return {
            'success': True,
            'user': user.to_dict(),
            'token': token
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        session.close()


def get_user_by_id(user_id: int) -> User:
    """Get user by ID"""
    session = Session()
    try:
        return session.query(User).filter(User.user_id == user_id).first()
    finally:
        session.close()


def update_user_password(user_id: int, old_password: str, new_password: str) -> dict:
    """Update user password"""
    session = Session()
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        # Verify old password
        if not verify_password(old_password, user.password_hash):
            return {'success': False, 'error': 'Current password is incorrect'}
        
        # Update password
        user.password_hash = hash_password(new_password)
        session.commit()
        
        return {'success': True, 'message': 'Password updated successfully'}
    except Exception as e:
        session.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        session.close()


def delete_user(user_id: int) -> dict:
    """Delete a user account"""
    session = Session()
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        session.delete(user)
        session.commit()
        
        return {'success': True, 'message': 'Account deleted successfully'}
    except Exception as e:
        session.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        session.close()


# Doctor-Patient relationship functions
def assign_patient_to_doctor(doctor_id: int, patient_id: int) -> dict:
    """Assign a patient to a doctor"""
    session = Session()
    try:
        doctor = session.query(User).filter(User.user_id == doctor_id, User.role == 'DOCTOR').first()
        if not doctor:
            return {'success': False, 'error': 'Doctor not found'}
        
        patient = session.query(User).filter(User.user_id == patient_id, User.role == 'PATIENT').first()
        if not patient:
            return {'success': False, 'error': 'Patient not found'}
        
        # Check if already assigned
        if patient in doctor.patients:
            return {'success': False, 'error': 'Patient already assigned to this doctor'}
        
        doctor.patients.append(patient)
        session.commit()
        
        return {'success': True, 'message': 'Patient assigned successfully'}
    except Exception as e:
        session.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        session.close()


def remove_patient_from_doctor(doctor_id: int, patient_id: int) -> dict:
    """Remove a patient from a doctor's list"""
    session = Session()
    try:
        doctor = session.query(User).filter(User.user_id == doctor_id, User.role == 'DOCTOR').first()
        if not doctor:
            return {'success': False, 'error': 'Doctor not found'}
        
        patient = session.query(User).filter(User.user_id == patient_id).first()
        if not patient:
            return {'success': False, 'error': 'Patient not found'}
        
        if patient not in doctor.patients:
            return {'success': False, 'error': 'Patient not assigned to this doctor'}
        
        doctor.patients.remove(patient)
        session.commit()
        
        return {'success': True, 'message': 'Patient removed successfully'}
    except Exception as e:
        session.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        session.close()


def get_doctor_patients(doctor_id: int) -> list:
    """Get all patients assigned to a doctor"""
    session = Session()
    try:
        doctor = session.query(User).filter(User.user_id == doctor_id, User.role == 'DOCTOR').first()
        if not doctor:
            return []
        
        return [patient.to_dict() for patient in doctor.patients]
    finally:
        session.close()


def get_patient_doctors(patient_id: int) -> list:
    """Get all doctors assigned to a patient"""
    session = Session()
    try:
        patient = session.query(User).filter(User.user_id == patient_id, User.role == 'PATIENT').first()
        if not patient:
            return []
        
        return [doctor.to_dict() for doctor in patient.doctors]
    finally:
        session.close()

