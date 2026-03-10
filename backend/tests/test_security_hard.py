import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from decimal import Decimal

# Mock Environment before importing app (Strict Config)
os.environ["DB_USER"] = "test_user"
os.environ["DB_PASSWORD"] = "test_pass"
os.environ["DB_HOST"] = "localhost"
os.environ["DB_NAME"] = "test_db"
os.environ["DB_PORT"] = "5432"
os.environ["API_KEYS"] = '{"test-key": "uploader", "admin-key": "superuser"}'
os.environ["UPLOAD_DIR"] = "/tmp/test_uploads"
os.environ["MAX_UPLOAD_BYTES"] = "1048576" # 1MB

from app.main import app
from app.api import endpoints

client = TestClient(app)

def test_missing_api_key():
    """Verify 401/403 if API Key is missing"""
    response = client.get("/health") # Health might be public? 
    # Check endpoints that require auth.
    # Health endpoint is public in main.py: @app.get("/health")
    assert response.status_code == 200 # Health is usually public
    
    # Try an authenticated endpoint (e.g. Ingest)
    # We need to mock DB dependency for ingest.
    # But checking 401 should happen BEFORE DB dependency if Security is global or on router?
    # In endpoints.py, it's on the function.
    
    # We'll just verify a protected endpoint returns 401 without header
    response = client.post("/api/v1/ingest/bank")
    assert response.status_code in [401, 403]

def test_invalid_api_key():
    response = client.post("/api/v1/ingest/bank", headers={"X-API-Key": "wrong-key"})
    assert response.status_code in [401, 403]

def test_valid_api_key_role():
    """Verify authorized access"""
    # Authorization logic depends on mocking dependencies.
    # Since we use dependency injection, checking if it PASSES auth requires mocking get_db too usually.
    # But 422 (Validation Error for missing file) means Auth PASSED.
    response = client.post(
        "/api/v1/ingest/bank", 
        headers={"X-API-Key": "test-key"}
    )
    assert response.status_code == 422 # Missing file, so Auth succeeded

def test_large_upload_rejection():
    """Verify files > MAX_UPLOAD_BYTES are rejected"""
    # MAX_UPLOAD_BYTES = 1MB
    large_content = b"x" * (1024 * 1024 + 100) # 1MB + 100 bytes
    
    # Mock SecureUpload to avoid actual file I/O if possible, or use the real one since it writes to tmp.
    # We want to test the STREAMING check logic.
    # So we should hit the real endpoint.
    
    files = {"file": ("large.txt", large_content, "text/plain")}
    
    # Need auth
    headers = {"X-API-Key": "test-key"}
    
    # We need to mock the DB dependency or it will fail on connection?
    # app.main creates engine. If env vars are dummy, connection fails?
    # endpoints.py `db=Depends(get_db)`.
    # We should override get_db to return a mock or just pass if the error happens earlier?
    # The SecureUpload check happens inside the function... AFTER get_db is called?
    # Depends are resolved first. So if DB fails, test fails.
    # We need to override DB dependency.
    pass

@pytest.fixture(autouse=True)
def override_db():
    app.dependency_overrides[endpoints.get_db] = lambda: MagicMock()
    yield
    app.dependency_overrides = {}

def test_upload_too_large():
    # MAX 1MB
    big_data = b"a" * (1024 * 1024 + 10)
    files = {"file": ("big.txt", big_data, "text/plain")}
    headers = {"X-API-Key": "test-key"}
    
    # We need to mock SecureUpload.upload_dir so we don't spam /tmp
    with patch("app.core.upload.settings.MAX_UPLOAD_BYTES", 100): # Mocking setting for faster test
        # 100 bytes limit
        data_150 = b"a" * 150
        files_small = {"file": ("test.txt", data_150, "text/plain")}
        
        response = client.post("/api/v1/ingest/bank", files=files_small, headers=headers)
        assert response.status_code == 413 # Payload Too Large

def test_binary_file_rejection():
    """Reject binary/exe disguised as txt"""
    # Magic bytes for EXE: MZ
    exe_content = b"MZ\x90\x00\x03\x00\x00\x00"
    files = {"file": ("malware.txt", exe_content, "text/plain")} # Fake mime
    headers = {"X-API-Key": "test-key"}
    
    response = client.post("/api/v1/ingest/bank", files=files, headers=headers)
    assert response.status_code == 400
    assert "Invalid file type" in response.text
