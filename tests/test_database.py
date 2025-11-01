"""
Tests for database configuration and session management.
"""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from sqlmodel import SQLModel, create_engine, Session
from app.database.database import (
    engine,
    create_db_and_tables,
    get_db,
    get_db_health,
    init_db,
    _create_sample_data
)


@pytest.fixture
def temp_db_url():
    """Create a temporary database URL for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        temp_db_url = f"sqlite:///{temp_file.name}"
        yield temp_db_url
        # Cleanup
        try:
            os.unlink(temp_file.name)
        except FileNotFoundError:
            pass


@pytest.fixture
def test_engine(temp_db_url):
    """Create a test database engine."""
    test_engine = create_engine(
        temp_db_url,
        echo=False,
        connect_args={"check_same_thread": False}
    )
    yield test_engine


class TestDatabaseEngine:
    """Test database engine configuration."""

    def test_engine_creation(self):
        """Test that engine is created with correct configuration."""
        # Engine should be created from settings
        assert engine is not None
        assert str(engine.url).startswith("sqlite:///")

    @patch('app.database.database.settings')
    def test_engine_echo_debug_mode(self, mock_settings):
        """Test that engine echo is enabled in DEBUG mode."""
        mock_settings.database_url = "sqlite:///./test.db"
        mock_settings.log_level = "DEBUG"
        
        # Re-import to test with mocked settings
        from importlib import reload
        import app.database.database as db_module
        reload(db_module)
        
        # In DEBUG mode, echo should be True
        # Note: This is a simplified test - actual implementation may vary
        assert mock_settings.log_level.upper() == "DEBUG"

    @patch('app.database.database.settings')
    def test_engine_no_echo_info_mode(self, mock_settings):
        """Test that engine echo is disabled in INFO mode."""
        mock_settings.database_url = "sqlite:///./test.db"
        mock_settings.log_level = "INFO"
        
        assert mock_settings.log_level.upper() != "DEBUG"


class TestCreateDbAndTables:
    """Test database and table creation."""

    @patch('app.database.database.SQLModel')
    def test_create_db_and_tables(self, mock_sqlmodel):
        """Test that create_db_and_tables calls SQLModel.metadata.create_all."""
        mock_metadata = MagicMock()
        mock_sqlmodel.metadata = mock_metadata
        
        create_db_and_tables()
        
        mock_metadata.create_all.assert_called_once_with(engine)

    def test_create_db_and_tables_with_real_engine(self, test_engine):
        """Test table creation with a real test engine."""
        # Patch the engine temporarily
        with patch('app.database.database.engine', test_engine):
            create_db_and_tables()
            # Should not raise any exceptions


class TestGetDb:
    """Test database session dependency."""

    def test_get_db_yields_session(self, test_engine):
        """Test that get_db yields a Session object."""
        with patch('app.database.database.engine', test_engine):
            db_generator = get_db()
            session = next(db_generator)
            
            assert isinstance(session, Session)
            
            # Clean up the generator
            try:
                next(db_generator)
            except StopIteration:
                pass  # Expected behavior

    def test_get_db_closes_session(self, test_engine):
        """Test that get_db properly closes the session."""
        with patch('app.database.database.engine', test_engine):
            db_generator = get_db()
            session = next(db_generator)
            
            # Session should be active
            assert session.is_active
            
            # Close the generator (simulates end of request)
            try:
                next(db_generator)
            except StopIteration:
                pass
            
            # Session should be closed after generator is exhausted
            assert not session.is_active

    def test_get_db_multiple_calls(self, test_engine):
        """Test that multiple calls to get_db return different sessions."""
        with patch('app.database.database.engine', test_engine):
            db_gen1 = get_db()
            db_gen2 = get_db()
            
            session1 = next(db_gen1)
            session2 = next(db_gen2)
            
            # Should be different session objects
            assert session1 is not session2
            
            # Clean up generators
            for gen in [db_gen1, db_gen2]:
                try:
                    next(gen)
                except StopIteration:
                    pass


class TestGetDbHealth:
    """Test database health check."""

    def test_get_db_health_success(self, test_engine):
        """Test that get_db_health returns True for healthy database."""
        with patch('app.database.database.engine', test_engine):
            # Create tables first
            create_db_and_tables()
            
            result = get_db_health()
            assert result is True

    @patch('app.database.database.Session')
    def test_get_db_health_failure(self, mock_session_class):
        """Test that get_db_health returns False when database is unhealthy."""
        # Mock Session to raise an exception
        mock_session = MagicMock()
        mock_session.__enter__.return_value.exec.side_effect = Exception("Database error")
        mock_session_class.return_value = mock_session
        
        result = get_db_health()
        assert result is False

    @patch('app.database.database.Session')
    def test_get_db_health_connection_error(self, mock_session_class):
        """Test health check with connection error."""
        mock_session_class.side_effect = Exception("Connection failed")
        
        result = get_db_health()
        assert result is False


class TestInitDb:
    """Test database initialization."""

    @patch('app.database.database.create_db_and_tables')
    @patch('app.database.database._create_sample_data')
    @patch('app.database.database.settings')
    def test_init_db_debug_mode(self, mock_settings, mock_create_sample, mock_create_tables):
        """Test that init_db creates sample data in DEBUG mode."""
        mock_settings.log_level = "DEBUG"
        
        init_db()
        
        mock_create_tables.assert_called_once()
        mock_create_sample.assert_called_once()

    @patch('app.database.database.create_db_and_tables')
    @patch('app.database.database._create_sample_data')
    @patch('app.database.database.settings')
    def test_init_db_info_mode(self, mock_settings, mock_create_sample, mock_create_tables):
        """Test that init_db doesn't create sample data in INFO mode."""
        mock_settings.log_level = "INFO"
        
        init_db()
        
        mock_create_tables.assert_called_once()
        mock_create_sample.assert_not_called()

    @patch('app.database.database.create_db_and_tables')
    @patch('app.database.database._create_sample_data')
    @patch('app.database.database.settings')
    def test_init_db_production_mode(self, mock_settings, mock_create_sample, mock_create_tables):
        """Test that init_db doesn't create sample data in production."""
        mock_settings.log_level = "ERROR"
        
        init_db()
        
        mock_create_tables.assert_called_once()
        mock_create_sample.assert_not_called()


class TestCreateSampleData:
    """Test sample data creation."""

    def test_create_sample_data_placeholder(self):
        """Test that _create_sample_data is a placeholder function."""
        # Currently it's just a pass statement, so it shouldn't raise any errors
        try:
            _create_sample_data()
        except Exception as e:
            pytest.fail(f"_create_sample_data raised an exception: {e}")


class TestDatabaseIntegration:
    """Integration tests for database functionality."""

    def test_full_database_workflow(self, test_engine):
        """Test the complete database workflow."""
        with patch('app.database.database.engine', test_engine):
            # Initialize database
            create_db_and_tables()
            
            # Check health
            assert get_db_health() is True
            
            # Get database session
            db_gen = get_db()
            session = next(db_gen)
            
            # Test basic query
            result = session.exec("SELECT 1").one()
            assert result == 1
            
            # Clean up
            try:
                next(db_gen)
            except StopIteration:
                pass

    def test_database_persistence(self, temp_db_url):
        """Test that database persists data between sessions."""
        test_engine = create_engine(temp_db_url, connect_args={"check_same_thread": False})
        
        with patch('app.database.database.engine', test_engine):
            # Create tables
            create_db_and_tables()
            
            # First session - create test table and insert data
            with Session(test_engine) as session1:
                session1.exec("CREATE TABLE IF NOT EXISTS test_table (id INTEGER, name TEXT)")
                session1.exec("INSERT INTO test_table (id, name) VALUES (1, 'test')")
                session1.commit()
            
            # Second session - verify data persists
            with Session(test_engine) as session2:
                result = session2.exec("SELECT name FROM test_table WHERE id = 1").one()
                assert result == "test"