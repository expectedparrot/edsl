"""
Proxy key encryption module for creating encrypted tokens with Expected Parrot's public key.

This module provides functionality to encrypt/decrypt Expected Parrot API keys along with
parameters to create proxy keys that can be used for limited access with specific
constraints like maximum charge credits and duration.
"""

import json
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, NamedTuple
import subprocess
import tempfile
import os
from pathlib import Path


class ProxyKeyPayload(NamedTuple):
    """Structure for proxy key payload data."""
    ep_token: str
    creation_date: datetime
    max_charge_credits: float
    duration_seconds: int


class ProxyKeyEncryption:
    """
    Handles encryption/decryption of Expected Parrot keys with GPG for creating proxy keys.
    
    This class provides methods to encrypt/decrypt API keys along with usage parameters
    using Expected Parrot's GPG key pair. The encrypted payload can then be
    used as a proxy key with limited access permissions.
    """
    
    # Expected Parrot's test public key for development
    EP_PUBLIC_KEY = """-----BEGIN PGP PUBLIC KEY BLOCK-----

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
Zzj+KSVMaQIBi/qBIbtWbtl3j/Q=
=DXid
-----END PGP PUBLIC KEY BLOCK-----"""

    # Expected Parrot's test private key for development (normally this would only be on EP servers)
    EP_PRIVATE_KEY = """-----BEGIN PGP PRIVATE KEY BLOCK-----

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
MAj1/wnwZzj+KSVMaQIBi/qBIbtWbtl3j/Q=
=xZOV
-----END PGP PRIVATE KEY BLOCK-----"""
    
    def __init__(self, ep_public_key: Optional[str] = None):
        """
        Initialize the proxy key encryption handler.
        
        Args:
            ep_public_key: Expected Parrot's public GPG key. If not provided,
                          uses the default key embedded in the class.
        """
        self.ep_public_key = ep_public_key or self.EP_PUBLIC_KEY
        
    def create_proxy_key_payload(
        self,
        ep_token: str,
        max_charge_credits: float = 1000.0,
        duration_seconds: int = 15000,
        creation_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Create the payload dictionary for proxy key encryption.
        
        Args:
            ep_token: The Expected Parrot API token to encrypt
            max_charge_credits: Maximum credits that can be charged using this proxy key
            duration_seconds: Duration in seconds for which the proxy key is valid
            creation_date: When the proxy key was created (defaults to now)
            
        Returns:
            Dictionary containing the proxy key parameters
        """
        if creation_date is None:
            creation_date = datetime.now(timezone.utc)
            
        payload = {
            "EP_TOKEN": ep_token,
            "CREATION_DATE": creation_date.isoformat(),
            "MAX_CHARGE_CREDITS": max_charge_credits,
            "DURATION_SECONDS": duration_seconds
        }
        
        return payload
        
    def _check_gpg_available(self) -> bool:
        """
        Check if GPG is available on the system.
        
        Returns:
            True if GPG is available, False otherwise
        """
        try:
            result = subprocess.run(
                ["gpg", "--version"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
            
    def _encrypt_with_gpg(self, plaintext: str, public_key: str) -> str:
        """
        Encrypt plaintext using GPG with the provided public key.
        
        Args:
            plaintext: The text to encrypt
            public_key: The public key to use for encryption
            
        Returns:
            Base64-encoded encrypted data
            
        Raises:
            RuntimeError: If GPG is not available or encryption fails
        """
        if not self._check_gpg_available():
            raise RuntimeError(
                "GPG is not available on this system. Please install GPG to use proxy key encryption."
            )
            
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create temporary files for the public key and plaintext
            key_file = Path(temp_dir) / "public_key.asc"
            plaintext_file = Path(temp_dir) / "plaintext.txt"
            
            # Write the public key to a temporary file
            with open(key_file, 'w') as f:
                f.write(public_key)
                
            # Write the plaintext to a temporary file
            with open(plaintext_file, 'w') as f:
                f.write(plaintext)
                
            try:
                # Import the public key
                import_result = subprocess.run(
                    ["gpg", "--import", str(key_file)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if import_result.returncode != 0:
                    raise RuntimeError(f"Failed to import public key: {import_result.stderr}")
                    
                # Encrypt the plaintext
                encrypt_result = subprocess.run(
                    [
                        "gpg", 
                        "--trust-model", "always",
                        "--armor", 
                        "--encrypt", 
                        "--recipient", "Expected Parrot",  # This would be the actual key ID
                        str(plaintext_file)
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if encrypt_result.returncode != 0:
                    raise RuntimeError(f"GPG encryption failed: {encrypt_result.stderr}")
                    
                # Read the encrypted output
                encrypted_file = f"{plaintext_file}.asc"
                if not os.path.exists(encrypted_file):
                    raise RuntimeError("Encrypted file was not created")
                    
                with open(encrypted_file, 'r') as f:
                    encrypted_data = f.read()
                    
                # Encode as base64 for easier handling
                return base64.b64encode(encrypted_data.encode('utf-8')).decode('utf-8')
                
            except subprocess.TimeoutExpired:
                raise RuntimeError("GPG operation timed out")
            except Exception as e:
                raise RuntimeError(f"Encryption failed: {str(e)}")
                
    def encrypt_proxy_key(
        self,
        ep_token: str,
        max_charge_credits: float = 1000.0,
        duration_seconds: int = 15000,
        creation_date: Optional[datetime] = None
    ) -> str:
        """
        Create and encrypt a proxy key with the specified parameters.
        
        Args:
            ep_token: The Expected Parrot API token to encrypt
            max_charge_credits: Maximum credits that can be charged using this proxy key
            duration_seconds: Duration in seconds for which the proxy key is valid
            creation_date: When the proxy key was created (defaults to now)
            
        Returns:
            Base64-encoded encrypted proxy key
            
        Raises:
            ValueError: If ep_token is empty or invalid
            RuntimeError: If encryption fails
        """
        if not ep_token or not ep_token.strip():
            raise ValueError("EP token cannot be empty")
            
        # Create the payload
        payload = self.create_proxy_key_payload(
            ep_token=ep_token,
            max_charge_credits=max_charge_credits,
            duration_seconds=duration_seconds,
            creation_date=creation_date
        )
        
        # Convert payload to formatted string
        payload_text = "\n".join([
            f"EP_TOKEN:{payload['EP_TOKEN']}",
            f"CREATION_DATE:{payload['CREATION_DATE']}",
            f"MAX_CHARGE_CREDITS:{payload['MAX_CHARGE_CREDITS']}",
            f"DURATION_SECONDS:{payload['DURATION_SECONDS']}"
        ])
        
        # Encrypt the payload
        encrypted_proxy_key = self._encrypt_with_gpg(payload_text, self.ep_public_key)
        
        return encrypted_proxy_key
        
    def _decrypt_with_gpg(self, encrypted_data: str, private_key: str) -> str:
        """
        Decrypt data using GPG with the provided private key.
        
        Args:
            encrypted_data: Base64-encoded encrypted data
            private_key: The private key to use for decryption
            
        Returns:
            Decrypted plaintext
            
        Raises:
            RuntimeError: If GPG is not available or decryption fails
        """
        if not self._check_gpg_available():
            raise RuntimeError(
                "GPG is not available on this system. Please install GPG to use proxy key decryption."
            )
            
        # Decode the base64 data
        try:
            encrypted_message = base64.b64decode(encrypted_data.encode('utf-8')).decode('utf-8')
        except Exception as e:
            raise RuntimeError(f"Failed to decode base64 data: {str(e)}")
            
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create temporary files for the private key and encrypted message
            key_file = Path(temp_dir) / "private_key.asc"
            encrypted_file = Path(temp_dir) / "encrypted.asc"
            
            # Write the private key to a temporary file
            with open(key_file, 'w') as f:
                f.write(private_key)
                
            # Write the encrypted message to a temporary file
            with open(encrypted_file, 'w') as f:
                f.write(encrypted_message)
                
            try:
                # Import the private key
                import_result = subprocess.run(
                    ["gpg", "--import", str(key_file)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if import_result.returncode != 0:
                    raise RuntimeError(f"Failed to import private key: {import_result.stderr}")
                    
                # Decrypt the message
                decrypt_result = subprocess.run(
                    [
                        "gpg", 
                        "--quiet",
                        "--decrypt", 
                        str(encrypted_file)
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if decrypt_result.returncode != 0:
                    raise RuntimeError(f"GPG decryption failed: {decrypt_result.stderr}")
                    
                return decrypt_result.stdout
                
            except subprocess.TimeoutExpired:
                raise RuntimeError("GPG operation timed out")
            except Exception as e:
                raise RuntimeError(f"Decryption failed: {str(e)}")
                
    def decrypt_proxy_key(
        self, 
        encrypted_proxy_key: str,
        private_key: Optional[str] = None
    ) -> ProxyKeyPayload:
        """
        Decrypt and parse a proxy key.
        
        Args:
            encrypted_proxy_key: Base64-encoded encrypted proxy key
            private_key: Private key for decryption (uses default if not provided)
            
        Returns:
            ProxyKeyPayload with decrypted information
            
        Raises:
            ValueError: If the encrypted key is invalid or malformed
            RuntimeError: If decryption fails
        """
        if not encrypted_proxy_key or not encrypted_proxy_key.strip():
            raise ValueError("Encrypted proxy key cannot be empty")
            
        # Use default private key if not provided
        if private_key is None:
            private_key = self.EP_PRIVATE_KEY
            
        # Decrypt the payload
        decrypted_text = self._decrypt_with_gpg(encrypted_proxy_key, private_key)
        
        # Parse the decrypted payload
        try:
            payload_data = {}
            for line in decrypted_text.strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    payload_data[key.strip()] = value.strip()
                    
            # Validate required fields
            required_fields = ['EP_TOKEN', 'CREATION_DATE', 'MAX_CHARGE_CREDITS', 'DURATION_SECONDS']
            missing_fields = [field for field in required_fields if field not in payload_data]
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")
                
            # Convert types
            return ProxyKeyPayload(
                ep_token=payload_data['EP_TOKEN'],
                creation_date=datetime.fromisoformat(payload_data['CREATION_DATE']),
                max_charge_credits=float(payload_data['MAX_CHARGE_CREDITS']),
                duration_seconds=int(payload_data['DURATION_SECONDS'])
            )
            
        except Exception as e:
            raise ValueError(f"Failed to parse decrypted payload: {str(e)}")
            
    def is_proxy_key_expired(self, payload: ProxyKeyPayload) -> bool:
        """
        Check if a proxy key has expired based on its creation date and duration.
        
        Args:
            payload: The proxy key payload to check
            
        Returns:
            True if the key has expired, False otherwise
        """
        expiration_time = payload.creation_date + timedelta(seconds=payload.duration_seconds)
        return datetime.now(timezone.utc) > expiration_time
        
    def get_proxy_key_remaining_time(self, payload: ProxyKeyPayload) -> timedelta:
        """
        Get the remaining time before a proxy key expires.
        
        Args:
            payload: The proxy key payload to check
            
        Returns:
            Remaining time as a timedelta (negative if expired)
        """
        expiration_time = payload.creation_date + timedelta(seconds=payload.duration_seconds)
        return expiration_time - datetime.now(timezone.utc)
        
    def validate_proxy_key_format(self, encrypted_proxy_key: str) -> bool:
        """
        Validate that the provided string is a properly formatted encrypted proxy key.
        
        Args:
            encrypted_proxy_key: The encrypted proxy key to validate
            
        Returns:
            True if the format appears valid, False otherwise
        """
        try:
            # Try to decode from base64
            decoded = base64.b64decode(encrypted_proxy_key.encode('utf-8'))
            decoded_str = decoded.decode('utf-8')
            
            # Check if it contains PGP armor
            return '-----BEGIN PGP MESSAGE-----' in decoded_str and '-----END PGP MESSAGE-----' in decoded_str
            
        except Exception:
            return False


# Convenience function for direct use
def create_encrypted_proxy_key(
    ep_token: str,
    max_charge_credits: float = 1000.0,
    duration_seconds: int = 15000,
    ep_public_key: Optional[str] = None
) -> str:
    """
    Convenience function to create an encrypted proxy key.
    
    Args:
        ep_token: The Expected Parrot API token to encrypt
        max_charge_credits: Maximum credits that can be charged using this proxy key
        duration_seconds: Duration in seconds for which the proxy key is valid
        ep_public_key: Expected Parrot's public GPG key (optional)
        
    Returns:
        Base64-encoded encrypted proxy key
    """
    encryptor = ProxyKeyEncryption(ep_public_key)
    return encryptor.encrypt_proxy_key(
        ep_token=ep_token,
        max_charge_credits=max_charge_credits,
        duration_seconds=duration_seconds
    )