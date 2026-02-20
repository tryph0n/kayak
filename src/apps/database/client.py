"""Database client for PostgreSQL NeonDB operations.

This module provides a database client wrapper for SQLAlchemy operations.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.apps.database.models import Base
from src.settings import Settings


class DatabaseClient:
    """Database client for PostgreSQL operations.

    Attributes:
        engine: SQLAlchemy engine instance
        Session: Session factory for database connections
    """

    def __init__(self):
        """Initialize database client with connection from settings."""
        postgres_url = Settings.get_postgres_url()
        self.engine = create_engine(
            postgres_url,
            echo=False,  # Set to True for SQL query debugging
            pool_pre_ping=True,  # Verify connections before using
        )
        self.Session = sessionmaker(bind=self.engine)

    def recreate_tables(self):
        """Drop and recreate all tables to match current model schema.

        Use this when model columns have changed. All data is lost.
        """
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)

    def get_session(self):
        """Get a new database session.

        Returns:
            SQLAlchemy Session object for database operations.

        Example:
            >>> client = DatabaseClient()
            >>> session = client.get_session()
            >>> try:
            ...     session.add(destination)
            ...     session.commit()
            ... finally:
            ...     session.close()
        """
        return self.Session()

    def close(self):
        """Close database engine and cleanup connections."""
        self.engine.dispose()
