# qenvy AWS Parameter Store Backend

## Overview

Add AWS Systems Manager Parameter Store backend to qenvy, enabling secure sharing of configs (including secrets) across machines and team members via AWS infrastructure.

## Motivation

### Current Limitation

qenvy stores configs locally in `~/.config/<app_name>/` (XDG directories):

- Configs tied to single machine
- No way to share across machines or with team
- For tools storing secrets (like benchling-webhook), this is particularly painful

### Why Parameter Store?

AWS Systems Manager Parameter Store with **SecureString** type provides:

- **Free tier**: Standard parameters (4KB) are free up to 10,000 parameters
- **Low cost**: Advanced parameters (8KB) are $0.05/month
- **KMS encryption**: Same encryption as Secrets Manager
- **IAM integration**: Fine-grained access control
- **CloudTrail audit**: Full audit logging of all access
- **Simple**: No rotation complexity we don't need

### Why NOT Secrets Manager?

Secrets Manager costs $0.40/secret/month (8x more expensive) and only provides:

- 2KB extra storage (10KB vs 8KB) - unnecessary for configs
- Automatic rotation - not needed for config files

Parameter Store SecureString provides identical security at fraction of the cost.

## Requirements

### Functional Requirements

1. **Transparent storage backend selection**
   - Environment variable: `QENVY_STORAGE=parameter-store`
   - Apps work identically regardless of backend
   - Filesystem storage remains default (backward compatible)

2. **Secure field marking**
   - Apps declare which config fields contain secrets
   - Used for documentation and validation (not storage)
   - Entire profile stored as SecureString when using Parameter Store

3. **AWS authentication**
   - Use standard AWS SDK credential chain
   - Support AWS_PROFILE, IAM roles, environment variables
   - No custom auth mechanism

4. **Parameter naming**
   - Pattern: `/{app-name}/{profile-name}`
   - Example: `/benchling-webhook/sales`
   - Configurable prefix via `QENVY_PARAMETER_PREFIX`

5. **Profile operations**
   - All existing qenvy operations work identically
   - Read, write, create, delete, list profiles
   - Inheritance resolution works across backends

### Non-Functional Requirements

1. **Backward compatibility**
   - Filesystem storage remains default
   - No breaking changes to existing qenvy API
   - Apps without AWS credentials continue working

2. **Performance**
   - Acceptable latency for config operations (~100-500ms per call)
   - Leverage Parameter Store built-in caching

3. **Security**
   - All profiles stored as SecureString (KMS encrypted)
   - No plaintext secrets in logs or error messages
   - IAM permissions required for all operations

4. **Error handling**
   - Clear error messages for missing AWS credentials
   - Helpful messages for permission errors
   - Graceful degradation when Parameter Store unavailable

## Design

### Architecture Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                          App Layer                          │
│  (benchling-webhook, qen, or any qenvy-using app)          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Same API
                         │
┌────────────────────────▼────────────────────────────────────┐
│                      QenvyBase                              │
│          (business logic, validation, inheritance)          │
└─────────┬──────────────────────────────────┬────────────────┘
          │                                  │
          │ Storage primitives               │ Storage primitives
          │                                  │
┌─────────▼──────────────┐      ┌───────────▼────────────────┐
│   QenvyConfig          │      │  ParameterStoreConfig      │
│   (filesystem)         │      │  (AWS Parameter Store)     │
│                        │      │                            │
│ ~/.config/<app>/       │      │ /{app}/{profile}           │
│   <profile>/           │      │ Type: SecureString         │
│     config.toml        │      │ KMS encrypted              │
└────────────────────────┘      └────────────────────────────┘
```

### Storage Backend Selection

Environment variable driven, with fallback:

```python
QENVY_STORAGE = os.getenv("QENVY_STORAGE", "filesystem")

if QENVY_STORAGE == "parameter-store":
    storage = ParameterStoreConfig(app_name)
else:
    storage = QenvyConfig(app_name)
```

### Parameter Store Schema

**Parameter naming:**

```text
/{app-name}/{profile-name}

Examples:
  /benchling-webhook/default
  /benchling-webhook/sales
  /benchling-webhook/dev
  /qen/main
  /qen/my-project
```

**Parameter type:** SecureString (always)

**Parameter value:** JSON-encoded config

```json
{
  "quilt": {
    "stackArn": "arn:aws:cloudformation:...",
    "catalog": "demo.quiltdata.com"
  },
  "benchling": {
    "clientSecret": "dV8XqBtnJ8pDx1s_yGL_qQ",
    "tenant": "quilt-dtt"
  },
  "_metadata": {
    "created": "2025-11-06T11:15:07.856Z",
    "modified": "2025-11-06T13:02:21.750Z"
  },
  "_inherits": "default"
}
```

**KMS encryption:** Use default AWS-managed key `aws/ssm` (or custom KMS key via config)

### API Changes

#### 1. Secure Field Marking (Optional)

Apps can declare which fields contain secrets for documentation:

```python
from qenvy import QenvyConfig

config = QenvyConfig(
    app_name="benchling-webhook",
    secure_fields=[
        "benchling.clientSecret",
        "benchling.secretArn",
        "quilt.apiKey"
    ]
)
```

**Purpose:**

- Documentation (helps developers know which fields are sensitive)
- Validation (warn if secure fields set to empty/default values)
- Logging (can redact secure fields from debug output)

**Not used for:**

- Storage decisions (entire profile is SecureString in Parameter Store)
- Encryption (handled by Parameter Store KMS encryption)

#### 2. Storage Backend Factory (Internal)

```python
def create_storage(
    app_name: str,
    storage_type: str | None = None,
    config_dir: Path | str | None = None,
    **kwargs
) -> QenvyBase:
    """Create storage backend based on type.

    Args:
        app_name: Application name
        storage_type: "filesystem" or "parameter-store" (default: from env)
        config_dir: Config directory (filesystem only)
        **kwargs: Backend-specific options

    Returns:
        Storage backend instance
    """
    if storage_type is None:
        storage_type = os.getenv("QENVY_STORAGE", "filesystem")

    if storage_type == "parameter-store":
        return ParameterStoreConfig(app_name=app_name, **kwargs)
    else:
        return QenvyConfig(app_name=app_name, base_dir=config_dir, **kwargs)
```

### ParameterStoreConfig Implementation

```python
class ParameterStoreConfig(QenvyBase):
    """AWS Parameter Store storage backend.

    Stores profiles as SecureString parameters in AWS Systems Manager
    Parameter Store with KMS encryption.
    """

    def __init__(
        self,
        app_name: str,
        region: str | None = None,
        prefix: str | None = None,
        kms_key_id: str | None = None,
        tier: str = "Advanced",
    ):
        """Initialize Parameter Store storage.

        Args:
            app_name: Application name (used in parameter naming)
            region: AWS region (default: from AWS_DEFAULT_REGION env)
            prefix: Parameter name prefix (default: /{app_name})
            kms_key_id: KMS key for encryption (default: aws/ssm)
            tier: Parameter tier "Standard" (4KB) or "Advanced" (8KB)
        """
        self.app_name = app_name
        self.region = region or os.getenv("QENVY_AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        self.prefix = prefix or os.getenv("QENVY_PARAMETER_PREFIX") or f"/{app_name}"
        self.kms_key_id = kms_key_id
        self.tier = tier

        # Initialize boto3 SSM client
        self.ssm = boto3.client("ssm", region_name=self.region)

    def _get_parameter_name(self, profile: str) -> str:
        """Get Parameter Store parameter name for profile."""
        return f"{self.prefix}/{profile}"

    def _read_profile_raw(self, profile: str) -> ProfileConfig:
        """Read profile from Parameter Store."""
        param_name = self._get_parameter_name(profile)

        try:
            response = self.ssm.get_parameter(
                Name=param_name,
                WithDecryption=True  # Decrypt SecureString
            )
            value = response["Parameter"]["Value"]
            return json.loads(value)
        except self.ssm.exceptions.ParameterNotFound:
            raise ProfileNotFoundError(profile)
        except Exception as e:
            raise StorageError("read", param_name, str(e)) from e

    def _write_profile_raw(self, profile: str, config: ProfileConfig) -> None:
        """Write profile to Parameter Store as SecureString."""
        param_name = self._get_parameter_name(profile)
        value = json.dumps(config, indent=2)

        try:
            self.ssm.put_parameter(
                Name=param_name,
                Value=value,
                Type="SecureString",  # Always encrypted
                Tier=self.tier,
                KeyId=self.kms_key_id,
                Overwrite=True
            )
        except Exception as e:
            raise StorageError("write", param_name, str(e)) from e

    def _delete_profile_raw(self, profile: str) -> None:
        """Delete profile from Parameter Store."""
        param_name = self._get_parameter_name(profile)

        try:
            self.ssm.delete_parameter(Name=param_name)
        except self.ssm.exceptions.ParameterNotFound:
            raise ProfileNotFoundError(profile)
        except Exception as e:
            raise StorageError("delete", param_name, str(e)) from e

    def _list_profiles_raw(self) -> list[str]:
        """List all profiles by scanning Parameter Store."""
        profiles = []
        next_token = None

        try:
            while True:
                kwargs = {
                    "ParameterFilters": [
                        {
                            "Key": "Name",
                            "Option": "BeginsWith",
                            "Values": [f"{self.prefix}/"]
                        }
                    ],
                    "MaxResults": 50
                }
                if next_token:
                    kwargs["NextToken"] = next_token

                response = self.ssm.describe_parameters(**kwargs)

                for param in response.get("Parameters", []):
                    # Extract profile name from parameter name
                    # /app-name/profile-name -> profile-name
                    name = param["Name"]
                    if name.startswith(f"{self.prefix}/"):
                        profile = name[len(f"{self.prefix}/"):]
                        profiles.append(profile)

                next_token = response.get("NextToken")
                if not next_token:
                    break

            return profiles
        except Exception as e:
            raise StorageError("list", self.prefix, str(e)) from e

    def _profile_exists_raw(self, profile: str) -> bool:
        """Check if profile exists in Parameter Store."""
        param_name = self._get_parameter_name(profile)

        try:
            self.ssm.describe_parameters(
                ParameterFilters=[
                    {
                        "Key": "Name",
                        "Values": [param_name]
                    }
                ]
            )
            return True
        except Exception:
            return False

    def _get_profile_path(self, profile: str) -> str:
        """Get parameter name (path) for profile."""
        return self._get_parameter_name(profile)

    def get_base_dir(self) -> str:
        """Get parameter prefix (equivalent of base directory)."""
        return self.prefix
```

### Environment Variables

```bash
# Storage backend selection
export QENVY_STORAGE=parameter-store  # or "filesystem" (default)

# AWS configuration
export QENVY_AWS_REGION=us-east-1     # AWS region
export AWS_PROFILE=my-profile         # AWS credentials profile

# Optional: Custom parameter naming
export QENVY_PARAMETER_PREFIX=/my-app  # Default: /{app-name}

# Optional: Custom KMS key
export QENVY_KMS_KEY_ID=arn:aws:kms:...  # Default: aws/ssm
```

## Implementation Plan

### Phase 1: Core Infrastructure

1. **Create `src/qenvy/parameter_store.py`**
   - Implement `ParameterStoreConfig(QenvyBase)`
   - Implement all storage primitives
   - Add boto3 dependency

2. **Add storage factory**
   - Create `src/qenvy/factory.py`
   - Implement `create_storage()` function
   - Environment variable detection

3. **Update dependencies**
   - Add `boto3` to `pyproject.toml`
   - Add `botocore` for typing
   - Optional dependency group for AWS

### Phase 2: API Enhancement

1. **Add secure field marking**
   - Add `secure_fields` parameter to `QenvyBase.__init__()`
   - Store as instance variable
   - Use for validation and logging (future)

2. **Update documentation**
   - README with Parameter Store examples
   - API reference for new classes
   - Migration guide from filesystem

### Phase 3: Testing

1. **Unit tests**
   - Mock boto3 SSM client
   - Test all storage operations
   - Test error handling

2. **Integration tests**
   - Require AWS credentials (skip if not available)
   - Test against real Parameter Store
   - Test profile operations end-to-end

3. **Cross-backend tests**
   - Test migration from filesystem to Parameter Store
   - Test inheritance across backends

### Phase 4: Application Integration

1. **Update benchling-webhook**
   - Add secure field declarations
   - Document Parameter Store usage
   - Update deployment scripts

2. **Update qen**
   - Consider Parameter Store for project configs
   - Document team sharing workflows

## Usage Examples

### Basic Usage (Transparent)

```python
# App code remains identical
from qenvy import QenvyConfig

config = QenvyConfig(app_name="my-app")
profile = config.read_profile("production")
```

```bash
# Filesystem (default)
python my_app.py

# Parameter Store (via env var)
export QENVY_STORAGE=parameter-store
export AWS_PROFILE=my-team
python my_app.py
```

### Marking Secure Fields

```python
from qenvy import QenvyConfig

config = QenvyConfig(
    app_name="benchling-webhook",
    secure_fields=[
        "benchling.clientSecret",
        "benchling.secretArn",
        "quilt.apiKey"
    ]
)

# Read profile (works with any backend)
profile = config.read_profile("sales")
```

### Migration from Filesystem

```bash
# 1. Export existing config to JSON
cat ~/.config/benchling-webhook/sales/config.json

# 2. Set up Parameter Store
export QENVY_STORAGE=parameter-store
export AWS_PROFILE=my-profile

# 3. Write config via Python
python -c "
from qenvy import create_storage
import json

with open('$HOME/.config/benchling-webhook/sales/config.json') as f:
    config = json.load(f)

storage = create_storage('benchling-webhook')
storage.write_profile('sales', config)
"

# 4. Verify
python -c "
from qenvy import create_storage
storage = create_storage('benchling-webhook')
print(storage.read_profile('sales'))
"
```

### Team Sharing Setup

```bash
# Team member A: Create shared config
export QENVY_STORAGE=parameter-store
export AWS_PROFILE=team-admin
python my_app.py setup

# Team member B: Use shared config (read-only IAM)
export QENVY_STORAGE=parameter-store
export AWS_PROFILE=team-dev
python my_app.py run
```

### IAM Permissions

**Minimum permissions for read-only access:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:DescribeParameters"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/benchling-webhook/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt"
      ],
      "Resource": "arn:aws:kms:*:*:key/*",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": "ssm.us-east-1.amazonaws.com"
        }
      }
    }
  ]
}
```

**Permissions for read-write access:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:PutParameter",
        "ssm:DeleteParameter",
        "ssm:DescribeParameters"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/benchling-webhook/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt",
        "kms:Encrypt",
        "kms:GenerateDataKey"
      ],
      "Resource": "arn:aws:kms:*:*:key/*",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": "ssm.us-east-1.amazonaws.com"
        }
      }
    }
  ]
}
```

## Security Considerations

### Encryption

- **At rest**: All profiles stored as SecureString with KMS encryption
- **In transit**: HTTPS for all AWS API calls (boto3 default)
- **In memory**: Decrypted values only in app memory, never logged

### Access Control

- **IAM policies**: Fine-grained control per parameter path
- **KMS permissions**: Separate control over encryption/decryption
- **CloudTrail**: Full audit log of all access

### Best Practices

1. **Use separate AWS accounts** for different environments (dev/prod)
2. **Rotate secrets** periodically (manual process, not automated)
3. **Least privilege IAM** - developers get read-only, CI/CD gets read-write
4. **Monitor CloudTrail** for unexpected access patterns

## Cost Analysis

### Parameter Store Costs

**Standard tier (4KB):**

- Free up to 10,000 parameters
- Free throughput: Up to 40 TPS (more than enough)

**Advanced tier (8KB):**

- $0.05 per parameter per month
- Higher throughput available if needed

**Typical benchling-webhook deployment:**

- 5-10 profiles per team
- ~1.5KB per profile (fits in standard tier)
- **Cost: FREE**

If using advanced tier (8KB):

- 10 profiles × $0.05 = **$0.50/month**

### Comparison to Alternatives

| Solution | Cost/Month | Notes |
|----------|-----------|-------|
| Parameter Store (standard) | $0 | Free tier, 4KB limit |
| Parameter Store (advanced) | $0.50 | 8KB limit, 10 profiles |
| Secrets Manager | $4.00 | 10 profiles × $0.40 |
| S3 (with manual encryption) | $0.02 | Storage only, not secure by default |

## Success Criteria

1. **Backward compatible**: Filesystem storage still works (default)
2. **Zero code changes**: Apps work with env var switch only
3. **Fully encrypted**: All profiles stored as SecureString
4. **Team sharing**: Multiple users can read/write same configs
5. **Well tested**: Unit tests + integration tests with real AWS
6. **Documented**: README, API docs, migration guide

## Future Enhancements

1. **Migration CLI**: Tool to migrate configs between backends
2. **Config sync**: Sync between filesystem and Parameter Store
3. **Profile locking**: Prevent concurrent modifications
4. **Version history**: Track config changes over time (Parameter Store has built-in versions)
5. **Secrets rotation**: Helper for rotating secrets in-place
6. **DynamoDB backend**: For very large configs or advanced querying

## References

- [AWS Systems Manager Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
- [Parameter Store pricing](https://aws.amazon.com/systems-manager/pricing/)
- [boto3 SSM client](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ssm.html)
- [KMS encryption](https://docs.aws.amazon.com/kms/latest/developerguide/overview.html)
