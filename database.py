"""
PharmaCheck Database Models and Configuration
SQLAlchemy ORM models for MySQL database
"""

import os
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, BigInteger, String, Text, DateTime, 
    Enum, ForeignKey, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, scoped_session
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'mysql+mysqlconnector://root:password@localhost:3306/pharmacheck'
)

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600
)

# Create session factory
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

# Base class for models
Base = declarative_base()


class User(Base):
    """User model for authentication and role management"""
    __tablename__ = 'User'
    
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), nullable=False, unique=True)
    password_hash = Column(String(60), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    role = Column(Enum('PATIENT', 'DOCTOR'), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    search_history = relationship('SearchHistory', back_populates='user', cascade='all, delete-orphan')
    
    # Doctor-Patient relationships
    patients = relationship(
        'User',
        secondary='Doctor_Patient',
        primaryjoin='User.user_id == Doctor_Patient.c.doctor_id',
        secondaryjoin='User.user_id == Doctor_Patient.c.patient_id',
        backref='doctors'
    )
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Condition(Base):
    """Medical condition model"""
    __tablename__ = 'Condition'
    
    condition_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    url = Column(String(512))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    drugs = relationship('Drug', back_populates='condition')
    
    def to_dict(self):
        return {
            'condition_id': self.condition_id,
            'name': self.name,
            'description': self.description,
            'url': self.url
        }


class Drug(Base):
    """Drug model with interaction relationships"""
    __tablename__ = 'Drug'
    
    drug_id = Column(Integer, primary_key=True, autoincrement=True)
    condition_id = Column(Integer, ForeignKey('Condition.condition_id', onupdate='CASCADE', ondelete='SET NULL'))
    name = Column(String(255), nullable=False, unique=True)
    generic_name = Column(String(255))
    description = Column(Text)
    url = Column(String(512))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    condition = relationship('Condition', back_populates='drugs')
    drug_interactions = relationship('DrugInteraction', back_populates='drug', cascade='all, delete-orphan')
    food_interactions = relationship('FoodInteraction', back_populates='drug', cascade='all, delete-orphan')
    disease_interactions = relationship('DiseaseInteraction', back_populates='drug', cascade='all, delete-orphan')
    
    # Indexes
    __table_args__ = (
        Index('idx_drug_name', 'name'),
        Index('idx_drug_generic_name', 'generic_name'),
    )
    
    def to_dict(self):
        return {
            'drug_id': self.drug_id,
            'name': self.name,
            'generic_name': self.generic_name,
            'description': self.description,
            'url': self.url,
            'condition': self.condition.to_dict() if self.condition else None
        }


class Interaction(Base):
    """Drug-drug interaction model"""
    __tablename__ = 'Interaction'
    
    interaction_id = Column(Integer, primary_key=True, autoincrement=True)
    severity = Column(Enum('Major', 'Moderate', 'Minor', 'Unknown'), nullable=False)
    professional_description = Column(Text, nullable=False)
    patient_description = Column(Text)
    ai_description = Column(Text)
    url = Column(String(512))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    drug_interactions = relationship('DrugInteraction', back_populates='interaction', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'interaction_id': self.interaction_id,
            'severity': self.severity,
            'professional_description': self.professional_description,
            'patient_description': self.patient_description,
            'ai_description': self.ai_description,
            'url': self.url
        }


class DrugInteraction(Base):
    """Junction table for Drug-Interaction many-to-many relationship"""
    __tablename__ = 'Drug_Interaction'
    
    drug_id = Column(Integer, ForeignKey('Drug.drug_id', onupdate='CASCADE', ondelete='CASCADE'), primary_key=True)
    interaction_id = Column(Integer, ForeignKey('Interaction.interaction_id', onupdate='CASCADE', ondelete='CASCADE'), primary_key=True)
    interacting_drug_name = Column(String(255))
    
    # Relationships
    drug = relationship('Drug', back_populates='drug_interactions')
    interaction = relationship('Interaction', back_populates='drug_interactions')


class FoodInteraction(Base):
    """Food/Lifestyle interaction model"""
    __tablename__ = 'FoodInteraction'
    
    food_interaction_id = Column(Integer, primary_key=True, autoincrement=True)
    drug_id = Column(Integer, ForeignKey('Drug.drug_id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
    interaction_name = Column(String(255), nullable=False)
    severity = Column(Enum('Major', 'Moderate', 'Minor', 'Unknown'), nullable=False)
    hazard_level = Column(String(100))
    plausibility = Column(Enum('High', 'Moderate', 'Low', 'Unknown'))
    professional_description = Column(Text, nullable=False)
    patient_description = Column(Text)
    ai_description = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    drug = relationship('Drug', back_populates='food_interactions')
    
    # Indexes
    __table_args__ = (
        Index('idx_food_drug', 'drug_id'),
    )
    
    def to_dict(self):
        return {
            'food_interaction_id': self.food_interaction_id,
            'drug_id': self.drug_id,
            'interaction_name': self.interaction_name,
            'severity': self.severity,
            'hazard_level': self.hazard_level,
            'plausibility': self.plausibility,
            'professional_description': self.professional_description,
            'patient_description': self.patient_description,
            'ai_description': self.ai_description
        }


class DiseaseInteraction(Base):
    """Disease interaction model"""
    __tablename__ = 'DiseaseInteraction'
    
    disease_interaction_id = Column(Integer, primary_key=True, autoincrement=True)
    drug_id = Column(Integer, ForeignKey('Drug.drug_id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
    disease_name = Column(String(255), nullable=False)
    severity = Column(Enum('Major', 'Moderate', 'Minor', 'Unknown'), nullable=False)
    hazard_level = Column(String(100))
    plausibility = Column(Enum('High', 'Moderate', 'Low', 'Unknown'))
    applicable_conditions = Column(Text)
    professional_description = Column(Text, nullable=False)
    patient_description = Column(Text)
    ai_description = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    drug = relationship('Drug', back_populates='disease_interactions')
    
    # Indexes
    __table_args__ = (
        Index('idx_disease_drug', 'drug_id'),
    )
    
    def to_dict(self):
        return {
            'disease_interaction_id': self.disease_interaction_id,
            'drug_id': self.drug_id,
            'disease_name': self.disease_name,
            'severity': self.severity,
            'hazard_level': self.hazard_level,
            'plausibility': self.plausibility,
            'applicable_conditions': self.applicable_conditions,
            'professional_description': self.professional_description,
            'patient_description': self.patient_description,
            'ai_description': self.ai_description
        }


class SearchHistory(Base):
    """Search history tracking model"""
    __tablename__ = 'SearchHistory'
    
    search_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('User.user_id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
    query = Column(Text, nullable=False)
    search_type = Column(Enum('DRUG', 'CONDITION', 'INTERACTION', 'FOOD_INTERACTION', 'DISEASE_INTERACTION'), default='DRUG')
    search_data = Column(Text)  # JSON string of full search results
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    user = relationship('User', back_populates='search_history')
    
    # Indexes
    __table_args__ = (
        Index('idx_search_user', 'user_id'),
        Index('idx_search_created', 'created_at'),
    )
    
    def to_dict(self):
        return {
            'search_id': self.search_id,
            'user_id': self.user_id,
            'query': self.query,
            'search_type': self.search_type,
            'search_data': self.search_data,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# Doctor-Patient association table (defined separately for relationship)
from sqlalchemy import Table
Doctor_Patient = Table(
    'Doctor_Patient',
    Base.metadata,
    Column('doctor_id', Integer, ForeignKey('User.user_id', onupdate='CASCADE', ondelete='CASCADE'), primary_key=True),
    Column('patient_id', Integer, ForeignKey('User.user_id', onupdate='CASCADE', ondelete='CASCADE'), primary_key=True),
    Column('assigned_at', DateTime, nullable=False, default=datetime.utcnow)
)


def init_db():
    """Initialize the database tables"""
    Base.metadata.create_all(engine)


def get_session():
    """Get a new database session"""
    return Session()


def close_session():
    """Close the current session"""
    Session.remove()


# Database utility functions
def get_or_create_drug(session, name, url=None, generic_name=None):
    """Get existing drug or create new one"""
    drug = session.query(Drug).filter(Drug.name == name).first()
    if not drug:
        drug = Drug(name=name, url=url, generic_name=generic_name)
        session.add(drug)
        session.flush()
    return drug


def get_or_create_condition(session, name, url=None):
    """Get existing condition or create new one"""
    condition = session.query(Condition).filter(Condition.name == name).first()
    if not condition:
        condition = Condition(name=name, url=url)
        session.add(condition)
        session.flush()
    return condition


def search_drugs(session, query, limit=20):
    """Search drugs by name with prefix matching"""
    return session.query(Drug).filter(
        Drug.name.ilike(f'{query}%')
    ).limit(limit).all()


def search_conditions(session, query, limit=20):
    """Search conditions by name with prefix matching"""
    return session.query(Condition).filter(
        Condition.name.ilike(f'{query}%')
    ).limit(limit).all()


if __name__ == '__main__':
    # Initialize database when run directly
    init_db()
    print("Database tables created successfully!")

