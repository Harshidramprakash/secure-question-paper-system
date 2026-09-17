import os
import sys
import subprocess
from pathlib import Path

def run_config_script(inject_url=None):
    """Run a small script in a subprocess to check the resolved DB URI."""
    script_lines = [
        "import os",
        "import sys",
        "from unittest import mock",
        "original_load_dotenv = __import__('dotenv').load_dotenv",
    ]
    
    if inject_url:
        script_lines.extend([
            "def mock_load_dotenv(*args, **kwargs):",
            f"    os.environ['DATABASE_URL'] = '{inject_url}'",
            "    return True",
            "with mock.patch('dotenv.load_dotenv', side_effect=mock_load_dotenv):"
        ])
    else:
        script_lines.extend([
            "def mock_load_dotenv(*args, **kwargs):",
            "    if 'DATABASE_URL' in os.environ:",
            "        del os.environ['DATABASE_URL']",
            "    return True",
            "with mock.patch('dotenv.load_dotenv', side_effect=mock_load_dotenv):"
        ])

    script_lines.extend([
        "    import app",
        "    from app.config import BaseConfig",
        "    print(BaseConfig.SQLALCHEMY_DATABASE_URI)"
    ])
    
    project_root = Path(__file__).parent.parent
    return subprocess.run(
        [sys.executable, '-c', '\n'.join(script_lines)],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )

def test_config_loading_postgresql():
    """Test that a Postgres DATABASE_URL selects the PostgreSQL URI."""
    result = run_config_script('postgresql://user:pass@localhost/test_db')
    assert result.returncode == 0
    assert 'postgresql://user:pass@localhost/test_db' in result.stdout

def test_config_loading_sqlite_fallback():
    """Test that absent DATABASE_URL falls back to SQLite."""
    result = run_config_script(None)
    assert result.returncode == 0
    assert 'sqlite:///app.db' in result.stdout

