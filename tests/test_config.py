import pytest
from app.config import _fix_database_url

def test_fix_database_url_preserves_valid():
    url = "postgresql://user:pass@host:5432/db"
    assert _fix_database_url(url) == url

def test_fix_database_url_strips_whitespace():
    url = "  postgresql://user:pass@host:5432/db  \n"
    assert _fix_database_url(url) == "postgresql://user:pass@host:5432/db"

def test_fix_database_url_strips_quotes():
    url = "\"postgresql://user:pass@host:5432/db\""
    assert _fix_database_url(url) == "postgresql://user:pass@host:5432/db"
    
    url2 = "'postgresql://user:pass@host:5432/db'"
    assert _fix_database_url(url2) == "postgresql://user:pass@host:5432/db"

def test_fix_database_url_fixes_postgres_scheme():
    url = "postgres://user:pass@host/db"
    assert _fix_database_url(url) == "postgresql://user:pass@host/db"

def test_fix_database_url_fixes_postgresql_psycopg_scheme():
    url = "postgresql+psycopg://user:pass@host/db"
    assert _fix_database_url(url) == "postgresql://user:pass@host/db"

def test_fix_database_url_preserves_query_params():
    url = "postgres://user:pass@host/db?sslmode=require"
    assert _fix_database_url(url) == "postgresql://user:pass@host/db?sslmode=require"
    
    url2 = "postgresql+psycopg://user:pass@host/db?sslmode=require&pool_size=5"
    assert _fix_database_url(url2) == "postgresql://user:pass@host/db?sslmode=require&pool_size=5"

def test_fix_database_url_handles_none():
    assert _fix_database_url(None) is None
    assert _fix_database_url("") == ""

def test_production_config_validates_url(monkeypatch, caplog):
    import logging
    from flask import Flask
    from app.config import ProductionConfig
    
    caplog.set_level(logging.INFO, logger='app.config')
    app = Flask(__name__)
    
    # Missing DEV_AUTH_BYPASS (default is False), valid secret, valid enc key
    app.config['SECRET_KEY'] = 'x' * 64
    app.config['ENCRYPTION_KEY'] = 'y' * 64
    
    # Valid DB URL
    app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://user:pass@host/db"
    
    # Should not raise
    ProductionConfig.init_app(app)
    
    assert "parses=True" in caplog.text
    assert "scheme=postgresql" in caplog.text
    caplog.clear()
    
    # Invalid DB URL that fails make_url
    app.config['SQLALCHEMY_DATABASE_URI'] = "not_a_url"
    
    with pytest.raises(RuntimeError, match="PRODUCTION CONFIGURATION ERROR"):
        ProductionConfig.init_app(app)
        
    assert "parses=False" in caplog.text
