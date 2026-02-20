"""SQLAlchemy models for PostgreSQL database.

This module defines the database schema for destinations and hotels.
"""

from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Destination(Base):
    """Destination model representing cities with weather data.

    Attributes:
        city_id: Auto-generated primary key
        city_name: Unique city name (natural key in CSV)
        latitude: City latitude coordinate
        longitude: City longitude coordinate
        weather_score: Computed weather score (indexed for sorting)
        avg_temperature_7d: Average temperature over 7 days forecast
        avg_rain_probability: Average rain probability (0-100)
        avg_cloud_coverage: Average cloud coverage (0-100)
        forecast_count: Number of forecast data points used
        hotels: Relationship to associated hotels
    """

    __tablename__ = "destinations"

    city_id = Column(Integer, primary_key=True, autoincrement=True)
    city_name = Column(String(100), unique=True, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    weather_score = Column(Float, nullable=False, index=True)
    avg_temperature_7d = Column(Float)
    avg_rain_probability = Column(Float)
    avg_cloud_coverage = Column(Float)
    forecast_count = Column(Integer)

    # Relationship
    hotels = relationship("Hotel", back_populates="destination")

    def __repr__(self):
        return f"<Destination(city_id={self.city_id}, city_name='{self.city_name}', weather_score={self.weather_score})>"


class Hotel(Base):
    """Hotel model representing accommodations in destinations.

    Attributes:
        hotel_id: Auto-generated primary key
        city_id: Foreign key to destinations table
        hotel_name: Hotel name
        url: Booking URL
        score: Hotel rating/score (indexed for sorting)
        address: Hotel address
        description: Hotel description text (from JSON-LD or page content)
        latitude: Hotel-specific latitude (geocoded from address)
        longitude: Hotel-specific longitude (geocoded from address)
        destination: Relationship to parent destination
    """

    __tablename__ = "hotels"

    hotel_id = Column(Integer, primary_key=True, autoincrement=True)
    city_id = Column(Integer, ForeignKey("destinations.city_id"), nullable=False, index=True)
    hotel_name = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)
    score = Column(Float, index=True)
    address = Column(Text)
    description = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # Relationship
    destination = relationship("Destination", back_populates="hotels")

    def __repr__(self):
        return f"<Hotel(hotel_id={self.hotel_id}, hotel_name='{self.hotel_name}', city_id={self.city_id}, score={self.score})>"
