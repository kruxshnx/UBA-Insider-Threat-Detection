import hashlib
import os
import pandas as pd

class SecurityEngine:
    def __init__(self, salt: str = "chem_secret_salt_v1"):
        self.salt = salt
        # Simple RBAC Policies
        # Role -> Allowed Actions / Views
        self.rbac_policy = {
            "Admin": ["view_pii", "view_raw_logs", "export_full_report", "manage_users"],
            "Analyst": ["view_anonymized_report", "view_alerts"],
            "Viewer": ["view_dashboard"]
        }

    def mask_pii(self, value: str) -> str:
        """
        Mask PII using SHA-256 hashing with salt.
        Used for User IDs, IP addresses, etc.
        """
        if pd.isna(value):
            return value
        
        # Simple salt + hash
        raw = f"{self.salt}{value}".encode('utf-8')
        return hashlib.sha256(raw).hexdigest()[:12] # Return short hash

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
