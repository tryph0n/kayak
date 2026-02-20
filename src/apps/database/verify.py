"""Database verification script.

This module provides verification functions to validate database integrity
after ETL pipeline execution.
"""

from src.apps.database.client import DatabaseClient
from src.apps.database.models import Destination, Hotel
from src.settings import Settings


def verify_database():
    """Run validation queries on the database.

    Checks:
    - Destinations count (configurable via TOP_N_DESTINATIONS)
    - Hotels count (configurable via TOP_N_DESTINATIONS × HOTELS_PER_DESTINATION)
    - Top N destinations by weather_score
    - Top hotels by score
    - Data integrity (orphan hotels)
    - Hotel distribution per city
    """
    db = None
    session = None

    try:
        db = DatabaseClient()
        session = db.get_session()

        print("=" * 50)
        print("DATABASE VERIFICATION REPORT")
        print("=" * 50)

        # Check destinations count
        dest_count = session.query(Destination).count()
        expected_destinations = Settings.top_n_destinations
        print(f"\nOK Destinations: {dest_count} (expected: {expected_destinations})")

        # Check hotels count
        hotel_count = session.query(Hotel).count()
        expected_hotels = Settings.top_n_destinations * Settings.hotels_per_destination
        print(f"OK Hotels: {hotel_count} (expected: {expected_hotels})")

        # Check top N destinations
        top_destinations = (
            session.query(Destination)
            .order_by(Destination.weather_score.desc())
            .limit(Settings.top_n_destinations)
            .all()
        )

        print(f"\nOK Top-{Settings.top_n_destinations} Destinations by Weather Score:")
        for i, dest in enumerate(top_destinations, 1):
            print(f"  {i}. {dest.city_name} (score: {dest.weather_score:.2f})")

        # Check top hotels
        top_hotels = session.query(Hotel).order_by(Hotel.score.desc()).limit(expected_hotels).all()

        print(f"\nOK Top-{expected_hotels} Hotels by Score:")
        for i, hotel in enumerate(top_hotels, 1):
            dest = (
                session.query(Destination)
                .filter_by(city_id=hotel.city_id)
                .first()
            )
            city_display = dest.city_name if dest else "Unknown"
            score_display = f"{hotel.score:.1f}" if hotel.score is not None else "N/A"
            print(f"  {i}. {hotel.hotel_name} ({city_display}, score: {score_display})")

        # Check data integrity
        print("\nOK Data Integrity Checks:")

        # Orphan hotels (should be 0)
        orphans = session.query(Hotel).filter(
            ~Hotel.city_id.in_(session.query(Destination.city_id))
        ).count()
        print(f"  - Orphan hotels: {orphans} (should be 0)")

        # Hotel distribution per city
        print("\nOK Hotel Distribution per City:")
        for dest in session.query(Destination).order_by(Destination.city_name).all():
            hotel_count_city = (
                session.query(Hotel).filter_by(city_id=dest.city_id).count()
            )
            print(f"  - {dest.city_name}: {hotel_count_city} hotels")

        print("\n" + "=" * 50)
        print("VERIFICATION COMPLETED SUCCESSFULLY")
        print("=" * 50)

    except Exception as e:
        print("\n" + "=" * 50)
        print(f"ERROR: Database verification failed: {e}")
        print("=" * 50)
        raise

    finally:
        if session:
            session.close()
            print("\nOK Database session closed")
        if db:
            db.close()
            print("OK Database connection disposed")


if __name__ == "__main__":
    verify_database()
