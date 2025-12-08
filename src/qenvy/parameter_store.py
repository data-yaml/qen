"""
AWS Parameter Store storage implementation for configuration management.

This module provides ParameterStoreConfig, a concrete implementation of QenvyBase
that stores configurations in AWS Systems Manager Parameter Store with KMS encryption.
"""

import json
import os
from typing import Any

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError as e:
    raise ImportError(
        "boto3 is required for Parameter Store backend. "
        "Install with: pip install qen[aws] or pip install boto3"
    ) from e

from .base import QenvyBase
from .exceptions import ProfileNotFoundError, StorageError
from .types import ProfileConfig


class ParameterStoreConfig(QenvyBase):
    """AWS Parameter Store storage backend.

    Stores profiles as SecureString parameters in AWS Systems Manager
    Parameter Store with KMS encryption.

    Features:
        - KMS encryption for all profiles (SecureString type)
        - IAM-based access control
        - CloudTrail audit logging
        - Parameter Store caching
        - Cost-effective (free tier for standard parameters)

    Parameter Naming:
        /{app_name}/{profile_name}

        Examples:
            /benchling-webhook/default
            /benchling-webhook/sales
            /qen/main
    """

    def __init__(
        self,
        app_name: str,
        region: str | None = None,
        prefix: str | None = None,
        kms_key_id: str | None = None,
        tier: str = "Advanced",
        secure_fields: list[str] | None = None,
    ):
        """Initialize Parameter Store storage.

        Args:
            app_name: Application name (used in parameter naming)
            region: AWS region (default: from QENVY_AWS_REGION or AWS_DEFAULT_REGION env)
            prefix: Parameter name prefix (default: /{app_name})
            kms_key_id: KMS key for encryption (default: aws/ssm)
            tier: Parameter tier "Standard" (4KB) or "Advanced" (8KB)
            secure_fields: List of field paths that contain secrets

        Environment Variables:
            QENVY_AWS_REGION: Override AWS region
            AWS_DEFAULT_REGION: Default AWS region
            QENVY_PARAMETER_PREFIX: Custom parameter prefix
            QENVY_KMS_KEY_ID: Custom KMS key ID
        """
        super().__init__(secure_fields=secure_fields)

        self.app_name = app_name
        self.region = region or os.getenv("QENVY_AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        self.prefix = prefix or os.getenv("QENVY_PARAMETER_PREFIX") or f"/{app_name}"
        self.kms_key_id = kms_key_id or os.getenv("QENVY_KMS_KEY_ID")
        self.tier = tier

        # Initialize boto3 SSM client
        self.ssm = boto3.client("ssm", region_name=self.region)

    def _get_parameter_name(self, profile: str) -> str:
        """Get Parameter Store parameter name for profile.

        Args:
            profile: Profile name

        Returns:
            Full parameter name (e.g., /app-name/profile-name)
        """
        return f"{self.prefix}/{profile}"

    # ====================================================================
    # Storage Primitives Implementation
    # ====================================================================

    def _read_profile_raw(self, profile: str) -> ProfileConfig:
        """Read profile from Parameter Store.

        Args:
            profile: Profile name

        Returns:
            Raw profile configuration

        Raises:
            ProfileNotFoundError: If profile does not exist
            StorageError: If read operation fails
        """
        param_name = self._get_parameter_name(profile)

        try:
            response = self.ssm.get_parameter(
                Name=param_name,
                WithDecryption=True,  # Decrypt SecureString
            )
            value = response["Parameter"]["Value"]
            config: ProfileConfig = json.loads(value)
            return config
        except ClientError as e:
            if e.response["Error"]["Code"] == "ParameterNotFound":
                raise ProfileNotFoundError(
                    profile, self._build_profile_not_found_error(profile)
                ) from e
            raise StorageError("read", param_name, str(e)) from e
        except json.JSONDecodeError as e:
            raise StorageError("read", param_name, f"Invalid JSON: {e}") from e
        except Exception as e:
            raise StorageError("read", param_name, str(e)) from e

    def _write_profile_raw(self, profile: str, config: ProfileConfig) -> None:
        """Write profile to Parameter Store as SecureString.

        Args:
            profile: Profile name
            config: Configuration to write

        Raises:
            StorageError: If write operation fails
        """
        param_name = self._get_parameter_name(profile)
        value = json.dumps(config, indent=2)

        try:
            put_params: dict[str, Any] = {
                "Name": param_name,
                "Value": value,
                "Type": "SecureString",  # Always encrypted
                "Tier": self.tier,
                "Overwrite": True,
            }

            # Only add KeyId if specified (otherwise uses default aws/ssm)
            if self.kms_key_id:
                put_params["KeyId"] = self.kms_key_id

            self.ssm.put_parameter(**put_params)
        except Exception as e:
            raise StorageError("write", param_name, str(e)) from e

    def _delete_profile_raw(self, profile: str) -> None:
        """Delete profile from Parameter Store.

        Args:
            profile: Profile name

        Raises:
            ProfileNotFoundError: If profile does not exist
            StorageError: If delete operation fails
        """
        param_name = self._get_parameter_name(profile)

        try:
            self.ssm.delete_parameter(Name=param_name)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ParameterNotFound":
                raise ProfileNotFoundError(profile) from e
            raise StorageError("delete", param_name, str(e)) from e
        except Exception as e:
            raise StorageError("delete", param_name, str(e)) from e

    def _list_profiles_raw(self) -> list[str]:
        """List all profiles by scanning Parameter Store.

        Returns:
            List of profile names

        Raises:
            StorageError: If list operation fails
        """
        profiles = []
        next_token: str | None = None

        try:
            while True:
                kwargs: dict[str, Any] = {
                    "ParameterFilters": [
                        {"Key": "Name", "Option": "BeginsWith", "Values": [f"{self.prefix}/"]}
                    ],
                    "MaxResults": 50,
                }
                if next_token:
                    kwargs["NextToken"] = next_token

                response = self.ssm.describe_parameters(**kwargs)

                for param in response.get("Parameters", []):
                    # Extract profile name from parameter name
                    # /app-name/profile-name -> profile-name
                    name = param["Name"]
                    if name.startswith(f"{self.prefix}/"):
                        profile = name[len(f"{self.prefix}/") :]
                        profiles.append(profile)

                next_token = response.get("NextToken")
                if not next_token:
                    break

            return profiles
        except Exception as e:
            raise StorageError("list", self.prefix, str(e)) from e

    def _profile_exists_raw(self, profile: str) -> bool:
        """Check if profile exists in Parameter Store.

        Args:
            profile: Profile name

        Returns:
            True if profile exists, False otherwise
        """
        param_name = self._get_parameter_name(profile)

        try:
            response = self.ssm.describe_parameters(
                ParameterFilters=[{"Key": "Name", "Values": [param_name]}]
            )
            return len(response.get("Parameters", [])) > 0
        except Exception:
            return False

    def _get_profile_path(self, profile: str) -> str:
        """Get parameter name (path) for profile.

        Args:
            profile: Profile name

        Returns:
            Parameter name (e.g., /app-name/profile-name)
        """
        return self._get_parameter_name(profile)

    def get_base_dir(self) -> str:
        """Get parameter prefix (equivalent of base directory).

        Returns:
            Parameter prefix (e.g., /app-name)
        """
        return self.prefix
