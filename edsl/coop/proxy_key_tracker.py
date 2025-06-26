"""
Proxy key charge tracking system for monitoring usage and remaining balance.

This module provides functionality to track charges against proxy keys and
check remaining balances to ensure users don't exceed their limits.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, NamedTuple
import platformdirs

from .proxy_key_encryption import ProxyKeyPayload, ProxyKeyEncryption


class ChargeRecord(NamedTuple):
    """Structure for charge record data."""
    proxy_key_hash: str
    charge_amount: float
    charge_date: datetime
    description: str
    transaction_id: Optional[str] = None


class ProxyKeyBalance(NamedTuple):
    """Structure for proxy key balance information."""
    proxy_key_hash: str
    max_credits: float
    used_credits: float
    remaining_credits: float
    is_expired: bool
    expiration_date: datetime


class ProxyKeyTracker:
    """
    Tracks charges and balances for proxy keys.
    
    This class maintains a local database of proxy key usage to ensure
    that usage limits are respected and provides balance checking functionality.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the proxy key tracker.
        
        Args:
            db_path: Path to the SQLite database file. If not provided,
                    uses a default location in the user's config directory.
        """
        if db_path is None:
            config_dir = platformdirs.user_config_dir("edsl")
            Path(config_dir).mkdir(parents=True, exist_ok=True)
            db_path = str(Path(config_dir) / "proxy_key_tracker.db")
            
        self.db_path = db_path
        self._init_database()
        
    def _init_database(self):
        """Initialize the SQLite database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create proxy_keys table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS proxy_keys (
                    proxy_key_hash TEXT PRIMARY KEY,
                    max_credits REAL NOT NULL,
                    creation_date TEXT NOT NULL,
                    expiration_date TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create charges table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS charges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proxy_key_hash TEXT NOT NULL,
                    charge_amount REAL NOT NULL,
                    charge_date TEXT NOT NULL,
                    description TEXT,
                    transaction_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (proxy_key_hash) REFERENCES proxy_keys (proxy_key_hash)
                )
            """)
            
            # Create index for better query performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_charges_proxy_key 
                ON charges (proxy_key_hash)
            """)
            
            conn.commit()
            
    def _get_proxy_key_hash(self, encrypted_proxy_key: str) -> str:
        """
        Generate a hash for the proxy key for tracking purposes.
        
        Args:
            encrypted_proxy_key: The encrypted proxy key
            
        Returns:
            Hash string for the proxy key
        """
        import hashlib
        return hashlib.sha256(encrypted_proxy_key.encode('utf-8')).hexdigest()[:16]
        
    def register_proxy_key(
        self, 
        encrypted_proxy_key: str,
        payload: Optional[ProxyKeyPayload] = None
    ) -> str:
        """
        Register a proxy key for tracking.
        
        Args:
            encrypted_proxy_key: The encrypted proxy key to register
            payload: Optional pre-decrypted payload (will decrypt if not provided)
            
        Returns:
            The proxy key hash for tracking
            
        Raises:
            ValueError: If the proxy key is invalid or already expired
        """
        # Get the payload if not provided
        if payload is None:
            encryptor = ProxyKeyEncryption()
            payload = encryptor.decrypt_proxy_key(encrypted_proxy_key)
            
        # Check if key is already expired
        encryptor = ProxyKeyEncryption()
        if encryptor.is_proxy_key_expired(payload):
            raise ValueError("Proxy key has already expired")
            
        proxy_key_hash = self._get_proxy_key_hash(encrypted_proxy_key)
        
        # Calculate expiration date
        from datetime import timedelta
        expiration_date = payload.creation_date + timedelta(seconds=payload.duration_seconds)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Insert or replace proxy key record
            cursor.execute("""
                INSERT OR REPLACE INTO proxy_keys 
                (proxy_key_hash, max_credits, creation_date, expiration_date, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (
                proxy_key_hash,
                payload.max_charge_credits,
                payload.creation_date.isoformat(),
                expiration_date.isoformat()
            ))
            
            conn.commit()
            
        return proxy_key_hash
        
    def add_charge(
        self,
        encrypted_proxy_key: str,
        charge_amount: float,
        description: str = "",
        transaction_id: Optional[str] = None
    ) -> bool:
        """
        Add a charge to a proxy key.
        
        Args:
            encrypted_proxy_key: The encrypted proxy key to charge
            charge_amount: Amount to charge (in credits)
            description: Optional description of the charge
            transaction_id: Optional transaction ID for tracking
            
        Returns:
            True if charge was successful, False if insufficient balance
            
        Raises:
            ValueError: If proxy key is not registered or expired
        """
        proxy_key_hash = self._get_proxy_key_hash(encrypted_proxy_key)
        
        # Check if key is registered and get current balance
        balance = self.get_balance(encrypted_proxy_key)
        
        if balance.is_expired:
            raise ValueError("Proxy key has expired")
            
        if balance.remaining_credits < charge_amount:
            return False  # Insufficient balance
            
        # Add the charge
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO charges 
                (proxy_key_hash, charge_amount, charge_date, description, transaction_id)
                VALUES (?, ?, ?, ?, ?)
            """, (
                proxy_key_hash,
                charge_amount,
                datetime.now(timezone.utc).isoformat(),
                description,
                transaction_id
            ))
            
            conn.commit()
            
        return True
        
    def get_balance(self, encrypted_proxy_key: str) -> ProxyKeyBalance:
        """
        Get the current balance for a proxy key.
        
        Args:
            encrypted_proxy_key: The encrypted proxy key to check
            
        Returns:
            ProxyKeyBalance with current balance information
            
        Raises:
            ValueError: If proxy key is not registered
        """
        proxy_key_hash = self._get_proxy_key_hash(encrypted_proxy_key)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get proxy key info
            cursor.execute("""
                SELECT max_credits, expiration_date 
                FROM proxy_keys 
                WHERE proxy_key_hash = ? AND is_active = 1
            """, (proxy_key_hash,))
            
            key_info = cursor.fetchone()
            if not key_info:
                raise ValueError("Proxy key is not registered")
                
            max_credits, expiration_date_str = key_info
            expiration_date = datetime.fromisoformat(expiration_date_str)
            
            # Get total charges
            cursor.execute("""
                SELECT COALESCE(SUM(charge_amount), 0)
                FROM charges 
                WHERE proxy_key_hash = ?
            """, (proxy_key_hash,))
            
            used_credits = cursor.fetchone()[0]
            
        # Check if expired
        is_expired = datetime.now(timezone.utc) > expiration_date
        
        return ProxyKeyBalance(
            proxy_key_hash=proxy_key_hash,
            max_credits=max_credits,
            used_credits=used_credits,
            remaining_credits=max_credits - used_credits,
            is_expired=is_expired,
            expiration_date=expiration_date
        )
        
    def get_charge_history(
        self,
        encrypted_proxy_key: str,
        limit: Optional[int] = None
    ) -> List[ChargeRecord]:
        """
        Get the charge history for a proxy key.
        
        Args:
            encrypted_proxy_key: The encrypted proxy key to check
            limit: Optional limit on number of records to return
            
        Returns:
            List of ChargeRecord objects
        """
        proxy_key_hash = self._get_proxy_key_hash(encrypted_proxy_key)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT proxy_key_hash, charge_amount, charge_date, description, transaction_id
                FROM charges 
                WHERE proxy_key_hash = ?
                ORDER BY charge_date DESC
            """
            
            if limit:
                query += f" LIMIT {limit}"
                
            cursor.execute(query, (proxy_key_hash,))
            
            records = []
            for row in cursor.fetchall():
                records.append(ChargeRecord(
                    proxy_key_hash=row[0],
                    charge_amount=row[1],
                    charge_date=datetime.fromisoformat(row[2]),
                    description=row[3],
                    transaction_id=row[4]
                ))
                
        return records
        
    def deactivate_proxy_key(self, encrypted_proxy_key: str):
        """
        Deactivate a proxy key (mark as inactive).
        
        Args:
            encrypted_proxy_key: The encrypted proxy key to deactivate
        """
        proxy_key_hash = self._get_proxy_key_hash(encrypted_proxy_key)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE proxy_keys 
                SET is_active = 0 
                WHERE proxy_key_hash = ?
            """, (proxy_key_hash,))
            
            conn.commit()
            
    def cleanup_expired_keys(self) -> int:
        """
        Remove expired and inactive proxy keys from the database.
        
        Returns:
            Number of keys cleaned up
        """
        current_time = datetime.now(timezone.utc).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get expired keys
            cursor.execute("""
                SELECT proxy_key_hash FROM proxy_keys 
                WHERE expiration_date < ? OR is_active = 0
            """, (current_time,))
            
            expired_keys = [row[0] for row in cursor.fetchall()]
            
            if expired_keys:
                # Delete charges for expired keys
                cursor.execute(f"""
                    DELETE FROM charges 
                    WHERE proxy_key_hash IN ({','.join(['?' for _ in expired_keys])})
                """, expired_keys)
                
                # Delete expired keys
                cursor.execute(f"""
                    DELETE FROM proxy_keys 
                    WHERE proxy_key_hash IN ({','.join(['?' for _ in expired_keys])})
                """, expired_keys)
                
                conn.commit()
                
        return len(expired_keys)
        
    def get_active_keys_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all active proxy keys.
        
        Returns:
            Dictionary with summary statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get active keys count
            cursor.execute("""
                SELECT COUNT(*) FROM proxy_keys 
                WHERE is_active = 1 AND expiration_date > ?
            """, (datetime.now(timezone.utc).isoformat(),))
            
            active_count = cursor.fetchone()[0]
            
            # Get total credits and usage
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(pk.max_credits), 0) as total_max_credits,
                    COALESCE(SUM(c.charge_amount), 0) as total_used_credits
                FROM proxy_keys pk
                LEFT JOIN charges c ON pk.proxy_key_hash = c.proxy_key_hash
                WHERE pk.is_active = 1 AND pk.expiration_date > ?
            """, (datetime.now(timezone.utc).isoformat(),))
            
            credits_info = cursor.fetchone()
            total_max_credits, total_used_credits = credits_info
            
        return {
            "active_keys": active_count,
            "total_max_credits": total_max_credits,
            "total_used_credits": total_used_credits,
            "total_remaining_credits": total_max_credits - total_used_credits
        }


# Convenience functions
def register_proxy_key(encrypted_proxy_key: str) -> str:
    """
    Convenience function to register a proxy key for tracking.
    
    Args:
        encrypted_proxy_key: The encrypted proxy key to register
        
    Returns:
        The proxy key hash for tracking
    """
    tracker = ProxyKeyTracker()
    return tracker.register_proxy_key(encrypted_proxy_key)


def check_proxy_key_balance(encrypted_proxy_key: str) -> ProxyKeyBalance:
    """
    Convenience function to check proxy key balance.
    
    Args:
        encrypted_proxy_key: The encrypted proxy key to check
        
    Returns:
        ProxyKeyBalance with current balance information
    """
    tracker = ProxyKeyTracker()
    return tracker.get_balance(encrypted_proxy_key)


def charge_proxy_key(
    encrypted_proxy_key: str,
    amount: float,
    description: str = ""
) -> bool:
    """
    Convenience function to charge a proxy key.
    
    Args:
        encrypted_proxy_key: The encrypted proxy key to charge
        amount: Amount to charge (in credits)
        description: Optional description
        
    Returns:
        True if charge was successful, False if insufficient balance
    """
    tracker = ProxyKeyTracker()
    return tracker.add_charge(encrypted_proxy_key, amount, description)