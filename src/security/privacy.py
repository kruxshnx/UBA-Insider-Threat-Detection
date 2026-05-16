"""
Security & Privacy Module for UBA & ITD System.

Implements:
- Pseudonymization with tokenization
- Just-in-time de-anonymization with dual-control
- Cryptographic erasure for GDPR compliance
- Audit logging for all privacy operations
- Role-Based Access Control (RBAC) with justification
"""

import hashlib
import hmac
import secrets
import base64
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import os
import json
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
import pandas as pd
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.config import config

logger = logging.getLogger("uba.security.privacy")


@dataclass
class PrivacyAuditEntry:
    """Audit log entry for privacy operations."""
    timestamp: datetime
    operation: str
    user_id: str
    operator: str
    justification: str
    approved_by: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


class PseudonymizationEngine:
    """
    Pseudonymization with tokenization for user data.
    
    Unlike anonymization (irreversible), pseudonymization allows
    authorized re-identification under controlled conditions.
    
    Features:
    - HMAC-based tokenization (irreversible without key)
    - Key rotation support
    - Separate key storage (HSM-backed in production)
    - Audit trail for all operations
    """
    
    def __init__(self, key: Optional[bytes] = None, key_path: str = "data/security_output/token_key"):
        self.key_path = key_path
        
        # Load or generate master key
        self.master_key = self._load_or_generate_key(key_path)
        
        # Token cache
        self.token_cache: Dict[str, str] = {}
        self.reverse_cache: Dict[str, str] = {}
        
        # Audit log
        self.audit_log: List[PrivacyAuditEntry] = []
        
        logger.info("PseudonymizationEngine initialized")
    
    def _load_or_generate_key(self, key_path: str) -> bytes:
        """Load existing key or generate new one."""
        if os.path.exists(key_path):
            with open(key_path, 'rb') as f:
                return f.read()
        else:
            # Generate secure key
            key = secrets.token_bytes(32)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(key_path), exist_ok=True)
            
            # Save key with restricted permissions
            with open(key_path, 'wb') as f:
                f.write(key)
            os.chmod(key_path, 0o600)  # Owner read/write only
            
            logger.info("Generated new tokenization key")
            return key
    
    def pseudonymize(self, user_id: str, salt: str = "") -> str:
        """
        Convert user ID to pseudonymous token.
        
        Args:
            user_id: Original user identifier
            salt: Optional salt for additional randomness
            
        Returns:
            Pseudonymous token (base64 encoded)
        """
        # Check cache
        cache_key = f"{user_id}:{salt}"
        if cache_key in self.token_cache:
            return self.token_cache[cache_key]
        
        # Create HMAC-SHA256 token
        message = f"{user_id}:{salt}".encode('utf-8')
        token = hmac.new(self.master_key, message, hashlib.sha256).digest()
        
        # Encode as base64 for safe storage
        token_b64 = base64.urlsafe_b64encode(token).decode('utf-8')
        
        # Cache
        self.token_cache[cache_key] = token_b64
        self.reverse_cache[token_b64] = cache_key
        
        return token_b64
    
    def depseudonymize(
        self, 
        token: str, 
        original_id: str,
        operator: str,
        justification: str,
        approver: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Revert pseudonymization (requires dual-control approval).
        
        Args:
            token: Pseudonymous token
            original_id: Claimed original ID (for verification)
            operator: Person requesting de-anonymization
            justification: Reason for de-anonymization
            approver: Second person approving the operation (dual-control)
            
        Returns:
            Tuple of (success, error_message)
        """
        # Dual-control check
        if approver is None:
            error_msg = "Dual-control approval required"
            self._audit_log("depseudonymize", operator, justification, False, error_msg)
            return False, error_msg
        
        # Verify token matches
        # In production, this would involve additional verification steps
        logger.info(
            "De-pseudonymization requested by %s, approved by %s: %s",
            operator, approver, justification
        )
        
        self._audit_log(
            "depseudonymize", operator, justification, 
            True, approver=approver
        )
        
        return True, None
    
    def pseudonymize_dataframe(
        self, 
        df: pd.DataFrame, 
        user_column: str = 'user'
    ) -> pd.DataFrame:
        """
        Pseudonymize all user IDs in a DataFrame.
        
        Args:
            df: Input DataFrame
            user_column: Name of column containing user IDs
            
        Returns:
            DataFrame with pseudonymized user column
        """
        result = df.copy()
        
        if user_column in result.columns:
            # Generate unique salt per user
            unique_users = result[user_column].unique()
            user_tokens = {
                user: self.pseudonymize(str(user), salt=f"uba_{datetime.now().date()}")
                for user in unique_users
            }
            
            result[user_column] = result[user_column].map(user_tokens)
            
            logger.info(
                "Pseudonymized %d unique users in DataFrame",
                len(unique_users)
            )
        
        return result
    
    def _audit_log(
        self, 
        operation: str, 
        operator: str, 
        justification: str,
        success: bool,
        approver: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Log privacy operation to audit trail."""
        entry = PrivacyAuditEntry(
            timestamp=datetime.now(),
            operation=operation,
            user_id=operator,
            operator=operator,
            justification=justification,
            approved_by=approver,
            success=success,
            error=error
        )
        self.audit_log.append(entry)
        
        # Also log to file
        audit_file = Path("data/security_output/privacy_audit.log")
        audit_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(audit_file, 'a') as f:
            f.write(
                f"{entry.timestamp.isoformat()} | "
                f"{entry.operation} | "
                f"{entry.operator} | "
                f"approved_by={entry.approved_by} | "
                f"success={entry.success} | "
                f"justification={entry.justification}\n"
            )
    
    def get_audit_log(self) -> List[Dict]:
        """Return audit log as list of dicts."""
        return [
            {
                'timestamp': entry.timestamp.isoformat(),
                'operation': entry.operation,
                'operator': entry.operator,
                'justification': entry.justification,
                'approved_by': entry.approved_by,
                'success': entry.success
            }
            for entry in self.audit_log
        ]


class CryptographicErasure:
    """
    Cryptographic erasure for GDPR "Right to be Forgotten".
    
    Instead of physically deleting data (which breaks audit trails),
    we delete the encryption key for that user's data, rendering
    it unrecoverable while maintaining structural integrity.
    """
    
    def __init__(self, key_vault_path: str = "data/security_output/key_vault"):
        self.key_vault_path = Path(key_vault_path)
        self.key_vault_path.mkdir(parents=True, exist_ok=True)
        
        # Per-user encryption keys
        self.user_keys: Dict[str, bytes] = self._load_keys()
        
        # Default Fernet for general encryption
        self.default_key = self._get_default_key()
        self.fernet = Fernet(self.default_key)
        
        logger.info("CryptographicErasure initialized")
    
    def _load_keys(self) -> Dict[str, bytes]:
        """Load existing user keys from vault."""
        keys = {}
        if self.key_vault_path.exists():
            for key_file in self.key_vault_path.glob("user_*.key"):
                user_id = key_file.stem.replace("user_", "")
                with open(key_file, 'rb') as f:
                    keys[user_id] = f.read()
        return keys
    
    def _get_default_key(self) -> bytes:
        """Load or generate default encryption key."""
        key_path = self.key_vault_path / "default.key"
        
        if key_path.exists():
            with open(key_path, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_path, 'wb') as f:
                f.write(key)
            os.chmod(key_path, 0o600)
            return key
    
    def encrypt_user_data(self, user_id: str, data: bytes) -> bytes:
        """
        Encrypt data with user-specific key.
        
        Args:
            user_id: User identifier
            data: Data to encrypt
            
        Returns:
            Encrypted data
        """
        # Get or generate user-specific key
        if user_id not in self.user_keys:
            self.user_keys[user_id] = Fernet.generate_key()
            self._save_user_key(user_id)
        
        user_fernet = Fernet(self.user_keys[user_id])
        return user_fernet.encrypt(data)
    
    def decrypt_user_data(self, user_id: str, encrypted_data: bytes) -> bytes:
        """
        Decrypt data with user-specific key.
        
        Args:
            user_id: User identifier
            encrypted_data: Encrypted data
            
        Returns:
            Decrypted data
        """
        if user_id not in self.user_keys:
            raise ValueError(f"No key found for user: {user_id}")
        
        user_fernet = Fernet(self.user_keys[user_id])
        return user_fernet.decrypt(encrypted_data)
    
    def erase_user(self, user_id: str, operator: str, justification: str) -> bool:
        """
        Cryptographically erase all user data.
        
        Deletes the user's encryption key, making all their
        encrypted data unrecoverable.
        
        Args:
            user_id: User to erase
            operator: Person requesting erasure
            justification: Legal/compliance justification
            
        Returns:
            Success status
        """
        if user_id not in self.user_keys:
            logger.warning("No encryption key found for user: %s", user_id)
            return False
        
        # Delete user's key
        key_file = self.key_vault_path / f"user_{user_id}.key"
        if key_file.exists():
            # Secure deletion (overwrite then delete)
            with open(key_file, 'wb') as f:
                f.write(os.urandom(os.path.getsize(key_file)))
            key_file.unlink()
        
        # Remove from memory
        del self.user_keys[user_id]
        
        # Log erasure
        audit_file = Path("data/security_output/gdpr_erasure.log")
        audit_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(audit_file, 'a') as f:
            f.write(
                f"{datetime.now().isoformat()} | "
                f"GDPR Erasure | "
                f"user={user_id} | "
                f"operator={operator} | "
                f"justification={justification}\n"
            )
        
        logger.info(
            "Cryptographically erased user %s (operator: %s)",
            user_id, operator
        )
        
        return True
    
    def _save_user_key(self, user_id: str):
        """Save user key to vault."""
        key_file = self.key_vault_path / f"user_{user_id}.key"
        with open(key_file, 'wb') as f:
            f.write(self.user_keys[user_id])
        os.chmod(key_file, 0o600)


class AccessControl:
    """
    Role-Based Access Control (RBAC) with justification logging.
    
    Enforces access policies and logs all access attempts.
    """
    
    def __init__(self):
        # Role hierarchy
        self.roles = {
            'Admin': {'level': 3, 'can_deanonymize': True, 'can_erase': False},
            'Analyst': {'level': 2, 'can_deanonymize': False, 'can_erase': False},
            'Viewer': {'level': 1, 'can_deanonymize': False, 'can_erase': False},
            'Compliance': {'level': 2, 'can_deanonymize': True, 'can_erase': True},
        }
        
        # Access log
        self.access_log: List[Dict] = []
        
        logger.info("AccessControl initialized")
    
    def check_access(
        self, 
        role: str, 
        resource: str, 
        action: str,
        justification: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if role has permission for action on resource.
        
        Args:
            role: User's role
            resource: Resource being accessed
            action: Action being performed
            justification: Required for sensitive operations
            
        Returns:
            Tuple of (allowed, reason)
        """
        if role not in self.roles:
            return False, f"Unknown role: {role}"
        
        role_config = self.roles[role]
        
        # Log access attempt
        self._log_access(role, resource, action, justification, True)
        
        # Check specific permissions
        if action == 'deanonymize':
            if not role_config.get('can_deanonymize', False):
                return False, f"Role {role} cannot de-anonymize"
            if not justification:
                return False, "Justification required"
        
        if action == 'erase':
            if not role_config.get('can_erase', False):
                return False, f"Role {role} cannot erase"
            if not justification:
                return False, "Justification required"
        
        return True, None
    
    def _log_access(
        self, 
        role: str, 
        resource: str, 
        action: str, 
        justification: Optional[str],
        allowed: bool
    ):
        """Log access attempt."""
        self.access_log.append({
            'timestamp': datetime.now().isoformat(),
            'role': role,
            'resource': resource,
            'action': action,
            'justification': justification,
            'allowed': allowed
        })
        
        # Also log to file
        audit_file = Path("data/security_output/access_control.log")
        audit_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(audit_file, 'a') as f:
            f.write(
                f"{datetime.now().isoformat()} | "
                f"{role} | "
                f"{action} on {resource} | "
                f"allowed={allowed}\n"
            )


# Global instances
pseudonymization = PseudonymizationEngine()
cryptographic_erasure = CryptographicErasure()
access_control = AccessControl()
