import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.modules.infrastructure_platform.authentication.services.auth_service import (
    AuthenticationService,
)
from backend.app.modules.infrastructure_platform.authorization.services.role_service import (
    RoleManagementService,
)
from backend.app.modules.infrastructure_platform.encryption.services.cryptography_provider import (
    CryptographyProvider,
)
from backend.app.modules.infrastructure_platform.encryption.services.key_management_service import (
    KeyManagementService,
)
from backend.app.modules.infrastructure_platform.encryption.services.secret_management_service import (
    SecretManagementService,
)
from backend.app.modules.infrastructure_platform.encryption.models.encryption_models import (
    KeyStatus,
    SecretStatus,
)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        # Seed standard roles and permissions
        role_service = RoleManagementService(session)
        await role_service.initialize_standard_roles_and_permissions()
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cryptography_provider_authenticated_encryption():
    """Verify AES-256-GCM round-trip, AAD authentication, and tamper rejection."""
    key = CryptographyProvider.generate_key()
    plaintext = "SECRET_ALPHA_VANTAGE_KEY_2026_XYZ"
    aad = {"context": "UNIT_TEST", "owner": "M01"}

    # 1. Encrypt with AAD
    envelope = CryptographyProvider.encrypt(key, plaintext, aad_context=aad)
    assert envelope is not None
    assert "AES-256-GCM" in envelope

    # 2. Decrypt with matching AAD -> Success
    decrypted = CryptographyProvider.decrypt(key, envelope, expected_aad_context=aad)
    assert decrypted == plaintext

    # 3. Decrypt with altered AAD -> Rejection
    with pytest.raises(ValueError, match="AAD verification failed"):
        CryptographyProvider.decrypt(key, envelope, expected_aad_context={"context": "WRONG_CONTEXT"})

    # 4. Tampered ciphertext -> Authentication Tag Failure
    import json
    import base64
    payload = json.loads(envelope)
    tampered_bytes = bytearray(base64.b64decode(payload["data"]))
    tampered_bytes[0] ^= 0xFF # Flip bits
    payload["data"] = base64.b64encode(bytes(tampered_bytes)).decode("utf-8")
    tampered_envelope = json.dumps(payload)

    with pytest.raises(ValueError, match="Decryption failed"):
        CryptographyProvider.decrypt(key, tampered_envelope, expected_aad_context=aad)


@pytest.mark.asyncio
async def test_key_management_lifecycle_and_rotation(db_session):
    """Verify DEK generation, KEK wrapping, key rotation, and version incrementation."""
    key_service = KeyManagementService(db_session)

    # 1. First get_active_key generates v1
    key_id_v1, raw_dek_v1 = await key_service.get_active_key()
    assert key_id_v1 is not None
    assert len(raw_dek_v1) == 32
    assert "v1" in key_id_v1

    # 2. Rotate keys -> v2 is generated and v1 is retired
    new_key_record = await key_service.rotate_keys()
    assert new_key_record.key_version == 2
    assert new_key_record.status == KeyStatus.ACTIVE

    key_id_v2, raw_dek_v2 = await key_service.get_active_key()
    assert key_id_v2 == new_key_record.key_id
    assert raw_dek_v1 != raw_dek_v2

    # 3. Historical key v1 is still decryptable by key_id
    retrieved_v1_dek = await key_service.get_key_by_id(key_id_v1)
    assert retrieved_v1_dek == raw_dek_v1


@pytest.mark.asyncio
async def test_secret_management_lifecycle(db_session):
    """Verify secret encryption, retrieval, rotation, and revocation."""
    secret_service = SecretManagementService(db_session)

    # 1. Create a secret
    secret = await secret_service.create_secret(
        secret_name="NSE Market Data Key",
        secret_type="API_KEY",
        owner_module="M01_FEED_REGISTRY",
        plaintext_value="NSE_SUPER_SECRET_TOKEN_4455",
    )
    assert secret.secret_id is not None
    assert secret.status == SecretStatus.ACTIVE
    assert secret.current_version == 1

    # 2. Retrieve plaintext
    plaintext = await secret_service.get_secret_plaintext(secret.secret_id)
    assert plaintext == "NSE_SUPER_SECRET_TOKEN_4455"

    # 3. Rotate secret
    rotated_secret = await secret_service.rotate_secret(
        secret_id=secret.secret_id,
        new_plaintext_value="NSE_ROTATED_TOKEN_8899",
    )
    assert rotated_secret.current_version == 2
    new_plaintext = await secret_service.get_secret_plaintext(secret.secret_id)
    assert new_plaintext == "NSE_ROTATED_TOKEN_8899"

    # 4. Revoke secret
    await secret_service.revoke_secret(secret.secret_id, reason="SCHEDULED_DECOMMISSION")
    with pytest.raises(ValueError, match="REVOKED"):
        await secret_service.get_secret_plaintext(secret.secret_id)


@pytest.mark.asyncio
async def test_api_security_encryption_endpoints(db_session, client):
    """Verify administrative endpoints under M15.05 RBAC enforcement."""
    auth_service = AuthenticationService(db_session)
    role_service = RoleManagementService(db_session)

    # Create admin user
    admin_user = await auth_service.create_user(
        username="sec_admin",
        password="SecAdminPassword2026!",
        display_name="Security Admin",
    )
    await role_service.assign_role_to_user(admin_user.user_id, "ADMINISTRATOR")

    # Login admin
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "sec_admin", "password": "SecAdminPassword2026!"},
    )
    token = login_resp.json()["session_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Health endpoint
    health_resp = await client.get("/api/v1/security/health", headers=headers)
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "OPERATIONAL"

    # 2. Create secret via API
    create_resp = await client.post(
        "/api/v1/security/secrets",
        json={
            "secret_name": "Bloomberg Terminal B-PIPE Secret",
            "secret_type": "API_KEY",
            "owner_module": "M02_INGESTION",
            "plaintext_value": "BBG_CRED_LIVE_9988",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    sec_data = create_resp.json()
    assert sec_data["secret_name"] == "Bloomberg Terminal B-PIPE Secret"
    assert "plaintext_value" not in sec_data
    assert "ciphertext_payload" not in sec_data # Plaintext and ciphertext never exposed in response
    sec_id = sec_data["secret_id"]

    # 3. List secrets
    list_resp = await client.get("/api/v1/security/secrets", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 4. Rotate Key via API
    rot_resp = await client.post("/api/v1/security/keys/rotate", headers=headers)
    assert rot_resp.status_code == 200
    assert rot_resp.json()["key_version"] >= 2
