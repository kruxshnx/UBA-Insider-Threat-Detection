import hashlib
import os
import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# PII masking salt.
#
# The salt is applied before hashing so that identical plaintext values do not
# hash to the same digest across deployments (which would allow rainbow-table /
# dictionary attacks and cross-tenant correlation). It MUST be configurable and
# kept secret in production.
#
# Resolution order:
#   1. UBA_PII_SALT environment variable (preferred; set per deployment)
#   2. explicit `salt=` argument to SecurityEngine(...)
#   3. DEFAULT_PII_SALT below (documented fallback ONLY for local/dev use)
#
# NOTE: the default is intentionally a placeholder. Override it in production by
# setting UBA_PII_SALT to a long, random, secret value. Changing the salt
# re-maps all masked identifiers, so keep it stable within a deployment.
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_PII_SALT = "uba_default_dev_salt_change_me"

# Length (in hex chars) of the returned masked digest. sha256 produces 64 hex
# chars; we keep a longer prefix than the original 12 to reduce collision risk
# while remaining compact. Override via UBA_PII_MASK_LENGTH.
DEFAULT_MASK_LENGTH = 32


class SecurityEngine:
    def __init__(self, salt: str = None, mask_length: int = None):
        # Salt: env var takes precedence, then explicit arg, then documented default.
        self.salt = os.environ.get("UBA_PII_SALT") or salt or DEFAULT_PII_SALT

        # Masked-digest length: env var, then arg, then default.
        env_len = os.environ.get("UBA_PII_MASK_LENGTH")
        if env_len and env_len.isdigit():
            self.mask_length = int(env_len)
        elif mask_length is not None:
            self.mask_length = mask_length
        else:
            self.mask_length = DEFAULT_MASK_LENGTH

        # Clamp to the 64 hex chars a sha256 digest provides.
        self.mask_length = max(1, min(self.mask_length, 64))

        # Simple RBAC Policies
        # Role -> Allowed Actions / Views
        self.rbac_policy = {
            "Admin": ["view_pii", "view_raw_logs", "export_full_report", "manage_users"],
            "Analyst": ["view_anonymized_report", "view_alerts"],
            "Viewer": ["view_dashboard"]
        }

    def mask_pii(self, value: str) -> str:
        """
        Mask PII using SHA-256 hashing with a configurable secret salt.
        Used for User IDs, IP addresses, etc.

        The salt is sourced from UBA_PII_SALT (env), the constructor argument,
        or a documented dev-only default (see DEFAULT_PII_SALT). A longer digest
        prefix (default 32 hex chars, configurable via UBA_PII_MASK_LENGTH) is
        returned to reduce collision risk. This remains a one-way transform;
        re-identification requires the pseudonymization engine, not this mask.
        """
        if pd.isna(value):
            return value

        # Salt + hash (salt kept secret / configurable per deployment)
        raw = f"{self.salt}{value}".encode('utf-8')
        return hashlib.sha256(raw).hexdigest()[:self.mask_length]  # Return masked hash

    def anonymize_dataframe(self, df: pd.DataFrame, columns_to_mask: list = ["user", "pc"]) -> pd.DataFrame:
        """
        Return a copy of the dataframe with specified columns masked.
        """
        df_masked = df.copy()
        for col in columns_to_mask:
            if col in df_masked.columns:
                df_masked[col] = df_masked[col].apply(self.mask_pii)
        return df_masked

    def check_access(self, role: str, action: str) -> bool:
        """
        Check if role is allowed to perform action.
        """
        allowed_actions = self.rbac_policy.get(role, [])
        return action in allowed_actions

    def get_view(self, df: pd.DataFrame, role: str) -> pd.DataFrame:
        """
        Return the appropriate view of the data based on role.
        Admin: Full View
        Analyst: Anonymized View
        """
        if self.check_access(role, "view_pii"):
            return df
        elif self.check_access(role, "view_anonymized_report"):
            return self.anonymize_dataframe(df)
        else:
            raise PermissionError(f"Role '{role}' is not allowed to view this data.")
