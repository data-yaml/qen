"""
Tests for qenvy Parameter Store implementation.

Tests AWS Parameter Store backend including:
- Parameter creation and reading
- SecureString encryption
- JSON serialization
- Error handling
- Parameter listing and deletion

These are UNIT TESTS using moto to mock AWS services.
Integration tests with real AWS are in tests/integration/.
"""

import json
from typing import Any

import boto3
import pytest
from moto import mock_aws

from qenvy.exceptions import (
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    StorageError,
)
from qenvy.parameter_store import ParameterStoreConfig


@pytest.fixture
def aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock AWS credentials for moto."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def parameter_store(aws_credentials: None) -> ParameterStoreConfig:
    """Provide ParameterStoreConfig instance with mocked AWS."""
    with mock_aws():
        yield ParameterStoreConfig("test-app", region="us-east-1")


@pytest.fixture
def parameter_store_with_prefix(aws_credentials: None) -> ParameterStoreConfig:
    """Provide ParameterStoreConfig with custom prefix."""
    with mock_aws():
        yield ParameterStoreConfig("test-app", region="us-east-1", prefix="/custom/prefix")


class TestParameterStoreInitialization:
    """Test ParameterStoreConfig initialization."""

    def test_init_with_defaults(self, aws_credentials: None) -> None:
        """Test initialization with default parameters."""
        with mock_aws():
            config = ParameterStoreConfig("my-app")

            assert config.app_name == "my-app"
            assert config.prefix == "/my-app"
            assert config.tier == "Advanced"
            assert config.kms_key_id is None

    def test_init_with_custom_prefix(self, aws_credentials: None) -> None:
        """Test initialization with custom prefix."""
        with mock_aws():
            config = ParameterStoreConfig("my-app", prefix="/custom/path")

            assert config.prefix == "/custom/path"

    def test_init_with_env_vars(
        self, aws_credentials: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test initialization with environment variables."""
        monkeypatch.setenv("QENVY_PARAMETER_PREFIX", "/env/prefix")
        monkeypatch.setenv("QENVY_AWS_REGION", "us-west-2")

        with mock_aws():
            config = ParameterStoreConfig("my-app")

            assert config.prefix == "/env/prefix"
            assert config.region == "us-west-2"

    def test_init_with_secure_fields(self, aws_credentials: None) -> None:
        """Test initialization with secure_fields parameter."""
        with mock_aws():
            config = ParameterStoreConfig("my-app", secure_fields=["api.key", "db.password"])

            assert config.secure_fields == ["api.key", "db.password"]


class TestParameterNaming:
    """Test parameter naming logic."""

    def test_get_parameter_name_default_prefix(self, aws_credentials: None) -> None:
        """Test parameter name with default prefix."""
        with mock_aws():
            config = ParameterStoreConfig("my-app")

            assert config._get_parameter_name("default") == "/my-app/default"
            assert config._get_parameter_name("prod") == "/my-app/prod"

    def test_get_parameter_name_custom_prefix(self, aws_credentials: None) -> None:
        """Test parameter name with custom prefix."""
        with mock_aws():
            config = ParameterStoreConfig("my-app", prefix="/custom")

            assert config._get_parameter_name("default") == "/custom/default"


class TestProfileCreation:
    """Test profile creation operations."""

    def test_create_empty_profile(self, parameter_store: ParameterStoreConfig) -> None:
        """Test creating an empty profile."""
        with mock_aws():
            # Need to recreate the SSM client within the mock context
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            parameter_store.create_profile("default")

            assert parameter_store.profile_exists("default")
            config = parameter_store.read_profile("default")
            assert isinstance(config, dict)
            assert "_metadata" in config

    def test_create_profile_with_config(self, parameter_store: ParameterStoreConfig) -> None:
        """Test creating a profile with initial configuration."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            initial_config = {
                "database": {
                    "host": "localhost",
                    "port": 5432,
                },
                "debug": True,
            }

            parameter_store.create_profile("dev", config=initial_config)

            config = parameter_store.read_profile("dev")
            assert config["database"]["host"] == "localhost"
            assert config["database"]["port"] == 5432
            assert config["debug"] is True

    def test_create_profile_already_exists(self, parameter_store: ParameterStoreConfig) -> None:
        """Test that creating existing profile raises error."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            parameter_store.create_profile("default")

            with pytest.raises(ProfileAlreadyExistsError) as exc_info:
                parameter_store.create_profile("default")

            assert exc_info.value.profile == "default"

    def test_create_profile_with_overwrite(self, parameter_store: ParameterStoreConfig) -> None:
        """Test overwriting existing profile."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            parameter_store.create_profile("default", config={"version": 1})
            parameter_store.create_profile("default", config={"version": 2}, overwrite=True)

            config = parameter_store.read_profile("default")
            assert config["version"] == 2

    def test_create_profile_stores_as_secure_string(
        self, parameter_store: ParameterStoreConfig
    ) -> None:
        """Test that profiles are stored as SecureString type."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            parameter_store.create_profile("default", config={"test": "value"})

            # Verify parameter type directly
            response = parameter_store.ssm.get_parameter(
                Name="/test-app/default", WithDecryption=False
            )
            assert response["Parameter"]["Type"] == "SecureString"


class TestProfileReading:
    """Test profile reading operations."""

    def test_read_profile_simple(self, parameter_store: ParameterStoreConfig) -> None:
        """Test reading a simple profile."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            config_data = {"key": "value", "number": 42}
            parameter_store.create_profile("test", config=config_data)

            config = parameter_store.read_profile("test")
            assert config["key"] == "value"
            assert config["number"] == 42

    def test_read_profile_not_found(self, parameter_store: ParameterStoreConfig) -> None:
        """Test reading non-existent profile raises error."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            with pytest.raises(ProfileNotFoundError) as exc_info:
                parameter_store.read_profile("nonexistent")

            assert exc_info.value.profile == "nonexistent"

    def test_read_profile_with_decryption(self, parameter_store: ParameterStoreConfig) -> None:
        """Test that profiles are decrypted when read."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            config_data = {"secret": "sensitive-value"}
            parameter_store.create_profile("secure", config=config_data)

            config = parameter_store.read_profile("secure")
            assert config["secret"] == "sensitive-value"

    def test_read_profile_with_inheritance(self, parameter_store: ParameterStoreConfig) -> None:
        """Test reading profile with inheritance resolution."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            # Create base profile
            parameter_store.create_profile("base", config={"base_key": "base_value", "shared": 1})

            # Create derived profile
            parameter_store.create_profile(
                "derived", config={"inherits": "base", "derived_key": "derived_value", "shared": 2}
            )

            config = parameter_store.read_profile("derived", resolve_inheritance=True)
            assert config["base_key"] == "base_value"
            assert config["derived_key"] == "derived_value"
            assert config["shared"] == 2  # Derived value overrides base


class TestProfileWriting:
    """Test profile writing operations."""

    def test_write_profile_simple(self, parameter_store: ParameterStoreConfig) -> None:
        """Test writing a simple profile."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            config_data = {"key": "value"}
            parameter_store.create_profile("test", config=config_data)

            # Update profile
            updated_config = {"key": "new_value", "new_key": "new"}
            parameter_store.write_profile("test", updated_config)

            config = parameter_store.read_profile("test")
            assert config["key"] == "new_value"
            assert config["new_key"] == "new"

    def test_write_profile_updates_metadata(self, parameter_store: ParameterStoreConfig) -> None:
        """Test that writing updates metadata timestamps."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            parameter_store.create_profile("test", config={"key": "value"})
            config_before = parameter_store.read_profile("test")
            created_before = config_before["_metadata"]["created"]
            modified_before = config_before["_metadata"]["modified"]

            # Small delay to ensure different timestamp
            import time

            time.sleep(0.01)

            # Write again - preserve existing config structure
            config_before["key"] = "updated"
            parameter_store.write_profile("test", config_before)
            config_after = parameter_store.read_profile("test")

            # Created should be preserved, modified should be updated
            assert config_after["_metadata"]["created"] == created_before
            assert config_after["_metadata"]["modified"] > modified_before
            assert config_after["key"] == "updated"


class TestProfileDeletion:
    """Test profile deletion operations."""

    def test_delete_profile(self, parameter_store: ParameterStoreConfig) -> None:
        """Test deleting a profile."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            parameter_store.create_profile("to-delete")
            assert parameter_store.profile_exists("to-delete")

            parameter_store.delete_profile("to-delete")
            assert not parameter_store.profile_exists("to-delete")

    def test_delete_profile_not_found(self, parameter_store: ParameterStoreConfig) -> None:
        """Test deleting non-existent profile raises error."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            with pytest.raises(ProfileNotFoundError):
                parameter_store.delete_profile("nonexistent")


class TestProfileListing:
    """Test profile listing operations."""

    def test_list_profiles_empty(self, parameter_store: ParameterStoreConfig) -> None:
        """Test listing profiles when none exist."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            profiles = parameter_store.list_profiles()
            assert profiles == []

    def test_list_profiles_multiple(self, parameter_store: ParameterStoreConfig) -> None:
        """Test listing multiple profiles."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            parameter_store.create_profile("default")
            parameter_store.create_profile("dev")
            parameter_store.create_profile("prod")

            profiles = parameter_store.list_profiles()
            assert sorted(profiles) == ["default", "dev", "prod"]

    def test_list_profiles_with_prefix_filter(
        self, parameter_store_with_prefix: ParameterStoreConfig
    ) -> None:
        """Test that profiles are filtered by prefix."""
        with mock_aws():
            parameter_store_with_prefix.ssm = boto3.client("ssm", region_name="us-east-1")

            # Create profiles with our prefix
            parameter_store_with_prefix.create_profile("profile1")
            parameter_store_with_prefix.create_profile("profile2")

            # Create profiles with different prefix (shouldn't be listed)
            ssm = boto3.client("ssm", region_name="us-east-1")
            ssm.put_parameter(
                Name="/different/prefix/other",
                Value=json.dumps({"test": "value"}),
                Type="SecureString",
            )

            profiles = parameter_store_with_prefix.list_profiles()
            assert sorted(profiles) == ["profile1", "profile2"]


class TestProfileExistence:
    """Test profile existence checks."""

    def test_profile_exists_true(self, parameter_store: ParameterStoreConfig) -> None:
        """Test checking existence of existing profile."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            parameter_store.create_profile("test")
            assert parameter_store.profile_exists("test")

    def test_profile_exists_false(self, parameter_store: ParameterStoreConfig) -> None:
        """Test checking existence of non-existent profile."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            assert not parameter_store.profile_exists("nonexistent")


class TestJSONSerialization:
    """Test JSON serialization and deserialization."""

    def test_serialize_complex_types(self, parameter_store: ParameterStoreConfig) -> None:
        """Test serialization of complex data types."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            config_data: dict[str, Any] = {
                "string": "text",
                "number": 42,
                "float": 3.14,
                "boolean": True,
                "null": None,
                "array": [1, 2, 3],
                "nested": {"key": "value"},
            }

            parameter_store.create_profile("complex", config=config_data)
            config = parameter_store.read_profile("complex")

            assert config["string"] == "text"
            assert config["number"] == 42
            assert config["float"] == 3.14
            assert config["boolean"] is True
            assert config["null"] is None
            assert config["array"] == [1, 2, 3]
            assert config["nested"]["key"] == "value"


class TestUtilityMethods:
    """Test utility methods."""

    def test_get_base_dir(self, parameter_store: ParameterStoreConfig) -> None:
        """Test get_base_dir returns prefix."""
        assert parameter_store.get_base_dir() == "/test-app"

    def test_get_profile_path(self, parameter_store: ParameterStoreConfig) -> None:
        """Test get_profile_path returns parameter name."""
        assert parameter_store._get_profile_path("default") == "/test-app/default"
        assert parameter_store._get_profile_path("prod") == "/test-app/prod"


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_read_invalid_json(self, parameter_store: ParameterStoreConfig) -> None:
        """Test reading parameter with invalid JSON raises StorageError."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            # Manually create parameter with invalid JSON
            parameter_store.ssm.put_parameter(
                Name="/test-app/invalid", Value="not valid json", Type="SecureString"
            )

            with pytest.raises(StorageError) as exc_info:
                parameter_store.read_profile("invalid")

            assert "Invalid JSON" in str(exc_info.value)

    def test_profile_not_found_error_message(self, parameter_store: ParameterStoreConfig) -> None:
        """Test ProfileNotFoundError has helpful message."""
        with mock_aws():
            parameter_store.ssm = boto3.client("ssm", region_name="us-east-1")

            # Create some profiles
            parameter_store.create_profile("profile1")
            parameter_store.create_profile("profile2")

            with pytest.raises(ProfileNotFoundError) as exc_info:
                parameter_store.read_profile("nonexistent")

            error_msg = str(exc_info.value)
            assert "nonexistent" in error_msg
            assert "profile1" in error_msg
            assert "profile2" in error_msg
