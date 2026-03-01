"""
SQLAlchemy models for Inter-Operator Agreement (IOA) database
"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Operator(Base):
    __tablename__ = 'operators'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    annotations = relationship('Annotation', back_populates='operator')

class Entity(Base):
    __tablename__ = 'entities'
    id = Column(Integer, primary_key=True)
    audio_file = Column(String, nullable=False)
    description = Column(Text)
    annotations = relationship('Annotation', back_populates='entity')

class Annotation(Base):
    __tablename__ = 'annotations'
    id = Column(Integer, primary_key=True)
    operator_id = Column(Integer, ForeignKey('operators.id'), nullable=False)
    entity_id = Column(Integer, ForeignKey('entities.id'), nullable=False)
    start_time = Column(Float, nullable=False)
    stop_time = Column(Float, nullable=False)
    label = Column(String, nullable=False)
    comments = Column(Text)
    timestamp = Column(DateTime)
    operator = relationship('Operator', back_populates='annotations')
    entity = relationship('Entity', back_populates='annotations')
