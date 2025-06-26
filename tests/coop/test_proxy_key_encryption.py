"""
Tests for proxy key encryption functionality.
"""

import pytest
import base64
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import tempfile
import os

from edsl.coop.proxy_key_encryption import (
    ProxyKeyEncryption, 
    ProxyKeyPayload,
    create_encrypted_proxy_key
)
from edsl.coop.proxy_key_tracker import (
    ProxyKeyTracker,
    ChargeRecord,
    ProxyKeyBalance
)
from edsl.coop import Coop


class TestProxyKeyEncryption:
    """Test cases for ProxyKeyEncryption class."""
    
    def test_init_with_default_key(self):
        """Test initialization with default public key."""
        encryptor = ProxyKeyEncryption()
        assert encryptor.ep_public_key == ProxyKeyEncryption.EP_PUBLIC_KEY
        
    def test_init_with_custom_key(self):
        """Test initialization with custom public key."""
        custom_key = "custom_public_key"
        encryptor = ProxyKeyEncryption(custom_key)
        assert encryptor.ep_public_key == custom_key
        
    def test_create_proxy_key_payload_with_defaults(self):
        """Test payload creation with default values."""
        encryptor = ProxyKeyEncryption()
        ep_token = "test_token_123"
        
        payload = encryptor.create_proxy_key_payload(ep_token)
        
        assert payload["EP_TOKEN"] == ep_token
        assert payload["MAX_CHARGE_CREDITS"] == 1000.0
        assert payload["DURATION_SECONDS"] == 15000
        assert "CREATION_DATE" in payload
        
        # Verify the creation date is recent
        creation_date = datetime.fromisoformat(payload["CREATION_DATE"])
        now = datetime.now(timezone.utc)
        time_diff = (now - creation_date).total_seconds()
        assert time_diff < 5  # Should be within 5 seconds
        
    def test_create_proxy_key_payload_with_custom_values(self):
        """Test payload creation with custom values."""
        encryptor = ProxyKeyEncryption()
        ep_token = "test_token_123"
        max_credits = 500.0
        duration = 3600
        custom_date = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        payload = encryptor.create_proxy_key_payload(
            ep_token=ep_token,
            max_charge_credits=max_credits,
            duration_seconds=duration,
            creation_date=custom_date
        )
        
        assert payload["EP_TOKEN"] == ep_token
        assert payload["MAX_CHARGE_CREDITS"] == max_credits
        assert payload["DURATION_SECONDS"] == duration
        assert payload["CREATION_DATE"] == custom_date.isoformat()
        
    @patch('subprocess.run')
    def test_check_gpg_available_success(self, mock_run):
        """Test GPG availability check when GPG is available."""
        mock_run.return_value.returncode = 0
        encryptor = ProxyKeyEncryption()
        
        assert encryptor._check_gpg_available() is True
        mock_run.assert_called_once_with(
            ["gpg", "--version"], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
    @patch('subprocess.run')
    def test_check_gpg_available_failure(self, mock_run):
        """Test GPG availability check when GPG is not available."""
        mock_run.return_value.returncode = 1
        encryptor = ProxyKeyEncryption()
        
        assert encryptor._check_gpg_available() is False
        
    @patch('subprocess.run')
    def test_check_gpg_available_file_not_found(self, mock_run):
        """Test GPG availability check when GPG command is not found."""
        mock_run.side_effect = FileNotFoundError()
        encryptor = ProxyKeyEncryption()
        
        assert encryptor._check_gpg_available() is False
        
    def test_encrypt_proxy_key_no_token(self):
        """Test encryption with empty token raises ValueError."""
        encryptor = ProxyKeyEncryption()
        
        with pytest.raises(ValueError, match="EP token cannot be empty"):
            encryptor.encrypt_proxy_key("")
            
        with pytest.raises(ValueError, match="EP token cannot be empty"):
            encryptor.encrypt_proxy_key("   ")
            
    @patch.object(ProxyKeyEncryption, '_check_gpg_available')
    def test_encrypt_proxy_key_no_gpg(self, mock_check_gpg):
        """Test encryption when GPG is not available."""
        mock_check_gpg.return_value = False
        encryptor = ProxyKeyEncryption()
        
        with pytest.raises(RuntimeError, match="GPG is not available"):
            encryptor.encrypt_proxy_key("test_token")
            
    @patch.object(ProxyKeyEncryption, '_encrypt_with_gpg')
    def test_encrypt_proxy_key_success(self, mock_encrypt_with_gpg):
        """Test successful encryption."""
        # Mock the encryption method to return a base64-encoded PGP message
        encrypted_content = "-----BEGIN PGP MESSAGE-----\nencrypted_content\n-----END PGP MESSAGE-----"
        mock_encrypt_with_gpg.return_value = base64.b64encode(encrypted_content.encode('utf-8')).decode('utf-8')
        
        encryptor = ProxyKeyEncryption()
        result = encryptor.encrypt_proxy_key("test_token")
        
        # Verify result is base64 encoded
        assert isinstance(result, str)
        decoded = base64.b64decode(result.encode('utf-8'))
        assert b"-----BEGIN PGP MESSAGE-----" in decoded
        
        # Verify the encrypt_with_gpg method was called with correct parameters
        mock_encrypt_with_gpg.assert_called_once()
        call_args = mock_encrypt_with_gpg.call_args[0]
        assert "EP_TOKEN:test_token" in call_args[0]
        assert "MAX_CHARGE_CREDITS:1000.0" in call_args[0]
        assert "DURATION_SECONDS:15000" in call_args[0]
        
    def test_validate_proxy_key_format_valid(self):
        """Test validation of a valid proxy key format."""
        encryptor = ProxyKeyEncryption()
        
        # Create a valid encrypted message
        valid_message = "-----BEGIN PGP MESSAGE-----\nencrypted_content\n-----END PGP MESSAGE-----"
        encoded_message = base64.b64encode(valid_message.encode('utf-8')).decode('utf-8')
        
        assert encryptor.validate_proxy_key_format(encoded_message) is True
        
    def test_validate_proxy_key_format_invalid(self):
        """Test validation of invalid proxy key formats."""
        encryptor = ProxyKeyEncryption()
        
        # Test various invalid formats
        assert encryptor.validate_proxy_key_format("invalid_format") is False
        assert encryptor.validate_proxy_key_format("") is False
        
        # Test base64 that doesn't contain PGP message
        invalid_content = base64.b64encode("not a pgp message".encode('utf-8')).decode('utf-8')
        assert encryptor.validate_proxy_key_format(invalid_content) is False
        
    def test_convenience_function(self):
        """Test the convenience function."""
        with patch.object(ProxyKeyEncryption, 'encrypt_proxy_key') as mock_encrypt:
            mock_encrypt.return_value = "encrypted_result"
            
            result = create_encrypted_proxy_key(
                ep_token="test_token",
                max_charge_credits=500.0,
                duration_seconds=3600
            )
            
            assert result == "encrypted_result"
            mock_encrypt.assert_called_once_with(
                ep_token="test_token",
                max_charge_credits=500.0,
                duration_seconds=3600
            )


class TestCoopProxyKeyIntegration:
    """Test integration of proxy key encryption with Coop class."""
    
    @patch('edsl.coop.ep_key_handling.ExpectedParrotKeyHandler.get_ep_api_key')
    def test_create_encrypted_proxy_key_no_api_key(self, mock_get_key):
        """Test proxy key creation when no API key is available."""
        mock_get_key.return_value = None
        coop = Coop(api_key=None)
        
        with pytest.raises(ValueError, match="No Expected Parrot API key available"):
            coop.create_encrypted_proxy_key()
            
    @patch.object(ProxyKeyEncryption, 'encrypt_proxy_key')
    def test_create_encrypted_proxy_key_success(self, mock_encrypt):
        """Test successful proxy key creation through Coop."""
        mock_encrypt.return_value = "encrypted_proxy_key"
        
        coop = Coop(api_key="test_api_key")
        result = coop.create_encrypted_proxy_key(
            max_charge_credits=500.0,
            duration_seconds=3600
        )
        
        assert result == "encrypted_proxy_key"
        mock_encrypt.assert_called_once_with(
            ep_token="test_api_key",
            max_charge_credits=500.0,
            duration_seconds=3600
        )
        
    @patch.object(ProxyKeyEncryption, 'encrypt_proxy_key')
    def test_create_encrypted_proxy_key_with_custom_public_key(self, mock_encrypt):
        """Test proxy key creation with custom public key."""
        mock_encrypt.return_value = "encrypted_proxy_key"
        custom_key = "custom_public_key"
        
        coop = Coop(api_key="test_api_key")
        result = coop.create_encrypted_proxy_key(
            ep_public_key=custom_key
        )
        
        assert result == "encrypted_proxy_key"
        # Verify that ProxyKeyEncryption was initialized with the custom key
        # This is verified through the mock call
        mock_encrypt.assert_called_once()


class TestProxyKeyDecryption:
    """Test cases for proxy key decryption functionality."""
    
    @patch.object(ProxyKeyEncryption, '_decrypt_with_gpg')
    def test_decrypt_proxy_key_success(self, mock_decrypt):
        """Test successful proxy key decryption."""
        # Mock decrypted payload
        mock_decrypt.return_value = """EP_TOKEN:test_token_123
CREATION_DATE:2023-01-01T12:00:00+00:00
MAX_CHARGE_CREDITS:1000.0
DURATION_SECONDS:3600"""
        
        encryptor = ProxyKeyEncryption()
        result = encryptor.decrypt_proxy_key("encrypted_key")
        
        assert isinstance(result, ProxyKeyPayload)
        assert result.ep_token == "test_token_123"
        assert result.max_charge_credits == 1000.0
        assert result.duration_seconds == 3600
        assert result.creation_date == datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
    def test_decrypt_proxy_key_empty_key(self):
        """Test decryption with empty key."""
        encryptor = ProxyKeyEncryption()
        
        with pytest.raises(ValueError, match="Encrypted proxy key cannot be empty"):
            encryptor.decrypt_proxy_key("")
            
    @patch.object(ProxyKeyEncryption, '_decrypt_with_gpg')
    def test_decrypt_proxy_key_invalid_format(self, mock_decrypt):
        """Test decryption with invalid payload format."""
        mock_decrypt.return_value = "invalid_format"
        
        encryptor = ProxyKeyEncryption()
        
        with pytest.raises(ValueError, match="Missing required fields"):
            encryptor.decrypt_proxy_key("encrypted_key")
            
    def test_is_proxy_key_expired(self):
        """Test proxy key expiration checking."""
        encryptor = ProxyKeyEncryption()
        
        # Create an expired payload
        expired_payload = ProxyKeyPayload(
            ep_token="test_token",
            creation_date=datetime.now(timezone.utc) - timedelta(hours=2),
            max_charge_credits=1000.0,
            duration_seconds=3600  # 1 hour
        )
        
        assert encryptor.is_proxy_key_expired(expired_payload) is True
        
        # Create a non-expired payload
        active_payload = ProxyKeyPayload(
            ep_token="test_token",
            creation_date=datetime.now(timezone.utc),
            max_charge_credits=1000.0,
            duration_seconds=3600  # 1 hour
        )
        
        assert encryptor.is_proxy_key_expired(active_payload) is False
        
    def test_get_proxy_key_remaining_time(self):
        """Test remaining time calculation."""
        encryptor = ProxyKeyEncryption()
        
        # Create a payload with known creation time
        now = datetime.now(timezone.utc)
        payload = ProxyKeyPayload(
            ep_token="test_token",
            creation_date=now,
            max_charge_credits=1000.0,
            duration_seconds=3600  # 1 hour
        )
        
        remaining = encryptor.get_proxy_key_remaining_time(payload)
        
        # Should be approximately 1 hour (allowing for small timing differences)
        assert 3590 <= remaining.total_seconds() <= 3600


class TestProxyKeyTracker:
    """Test cases for ProxyKeyTracker functionality."""
    
    def setup_method(self):
        """Set up test database."""
        import tempfile
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        self.tracker = ProxyKeyTracker(db_path=self.temp_db.name)
        
    def teardown_method(self):
        """Clean up test database."""
        import os
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
            
    @patch.object(ProxyKeyEncryption, 'decrypt_proxy_key')
    def test_register_proxy_key(self, mock_decrypt):
        """Test proxy key registration."""
        # Mock payload
        mock_payload = ProxyKeyPayload(
            ep_token="test_token",
            creation_date=datetime.now(timezone.utc),
            max_charge_credits=1000.0,
            duration_seconds=3600
        )
        mock_decrypt.return_value = mock_payload
        
        key_hash = self.tracker.register_proxy_key("encrypted_key")
        
        assert isinstance(key_hash, str)
        assert len(key_hash) == 16  # SHA256 truncated to 16 chars
        
    @patch.object(ProxyKeyEncryption, 'decrypt_proxy_key')
    def test_register_expired_proxy_key(self, mock_decrypt):
        """Test registration of expired proxy key."""
        # Mock expired payload
        mock_payload = ProxyKeyPayload(
            ep_token="test_token",
            creation_date=datetime.now(timezone.utc) - timedelta(hours=2),
            max_charge_credits=1000.0,
            duration_seconds=3600  # 1 hour, so expired
        )
        mock_decrypt.return_value = mock_payload
        
        with pytest.raises(ValueError, match="Proxy key has already expired"):
            self.tracker.register_proxy_key("encrypted_key")
            
    @patch.object(ProxyKeyEncryption, 'decrypt_proxy_key')
    def test_add_charge_success(self, mock_decrypt):
        """Test successful charge addition."""
        # Mock payload
        mock_payload = ProxyKeyPayload(
            ep_token="test_token",
            creation_date=datetime.now(timezone.utc),
            max_charge_credits=1000.0,
            duration_seconds=3600
        )
        mock_decrypt.return_value = mock_payload
        
        # Register key first
        self.tracker.register_proxy_key("encrypted_key")
        
        # Add charge
        success = self.tracker.add_charge("encrypted_key", 100.0, "Test charge")
        
        assert success is True
        
    @patch.object(ProxyKeyEncryption, 'decrypt_proxy_key')
    def test_add_charge_insufficient_balance(self, mock_decrypt):
        """Test charge addition with insufficient balance."""
        # Mock payload
        mock_payload = ProxyKeyPayload(
            ep_token="test_token",
            creation_date=datetime.now(timezone.utc),
            max_charge_credits=100.0,  # Low limit
            duration_seconds=3600
        )
        mock_decrypt.return_value = mock_payload
        
        # Register key first
        self.tracker.register_proxy_key("encrypted_key")
        
        # Try to charge more than available
        success = self.tracker.add_charge("encrypted_key", 200.0, "Large charge")
        
        assert success is False
        
    @patch.object(ProxyKeyEncryption, 'decrypt_proxy_key')
    def test_get_balance(self, mock_decrypt):
        """Test balance retrieval."""
        # Mock payload
        mock_payload = ProxyKeyPayload(
            ep_token="test_token",
            creation_date=datetime.now(timezone.utc),
            max_charge_credits=1000.0,
            duration_seconds=3600
        )
        mock_decrypt.return_value = mock_payload
        
        # Register key and add some charges
        self.tracker.register_proxy_key("encrypted_key")
        self.tracker.add_charge("encrypted_key", 100.0, "Charge 1")
        self.tracker.add_charge("encrypted_key", 200.0, "Charge 2")
        
        balance = self.tracker.get_balance("encrypted_key")
        
        assert isinstance(balance, ProxyKeyBalance)
        assert balance.max_credits == 1000.0
        assert balance.used_credits == 300.0
        assert balance.remaining_credits == 700.0
        assert balance.is_expired is False
        
    @patch.object(ProxyKeyEncryption, 'decrypt_proxy_key')
    def test_get_charge_history(self, mock_decrypt):
        """Test charge history retrieval."""
        # Mock payload
        mock_payload = ProxyKeyPayload(
            ep_token="test_token",
            creation_date=datetime.now(timezone.utc),
            max_charge_credits=1000.0,
            duration_seconds=3600
        )
        mock_decrypt.return_value = mock_payload
        
        # Register key and add charges
        self.tracker.register_proxy_key("encrypted_key")
        self.tracker.add_charge("encrypted_key", 100.0, "Charge 1")
        self.tracker.add_charge("encrypted_key", 200.0, "Charge 2")
        
        history = self.tracker.get_charge_history("encrypted_key")
        
        assert len(history) == 2
        assert all(isinstance(record, ChargeRecord) for record in history)
        assert history[0].charge_amount == 200.0  # Most recent first
        assert history[1].charge_amount == 100.0


class TestCoopProxyKeyIntegrationExtended:
    """Extended integration tests for Coop proxy key functionality."""
    
    @patch.object(ProxyKeyEncryption, 'decrypt_proxy_key')
    def test_decrypt_proxy_key_integration(self, mock_decrypt):
        """Test proxy key decryption through Coop."""
        mock_payload = ProxyKeyPayload(
            ep_token="test_token",
            creation_date=datetime.now(timezone.utc),
            max_charge_credits=1000.0,
            duration_seconds=3600
        )
        mock_decrypt.return_value = mock_payload
        
        coop = Coop(api_key="test_api_key")
        result = coop.decrypt_proxy_key("encrypted_key")
        
        assert result == mock_payload
        mock_decrypt.assert_called_once_with("encrypted_key")
        
    @patch.object(ProxyKeyTracker, 'register_proxy_key')
    def test_register_proxy_key_integration(self, mock_register):
        """Test proxy key registration through Coop."""
        mock_register.return_value = "key_hash_123"
        
        coop = Coop(api_key="test_api_key")
        result = coop.register_proxy_key_for_tracking("encrypted_key")
        
        assert result == "key_hash_123"
        mock_register.assert_called_once_with("encrypted_key")
        
    @patch.object(ProxyKeyTracker, 'get_balance')
    def test_check_proxy_key_balance_integration(self, mock_get_balance):
        """Test balance checking through Coop."""
        mock_balance = ProxyKeyBalance(
            proxy_key_hash="hash123",
            max_credits=1000.0,
            used_credits=300.0,
            remaining_credits=700.0,
            is_expired=False,
            expiration_date=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        mock_get_balance.return_value = mock_balance
        
        coop = Coop(api_key="test_api_key")
        result = coop.check_proxy_key_balance("encrypted_key")
        
        assert result == mock_balance
        mock_get_balance.assert_called_once_with("encrypted_key")
        
    @patch.object(ProxyKeyTracker, 'add_charge')
    def test_charge_proxy_key_integration(self, mock_add_charge):
        """Test proxy key charging through Coop."""
        mock_add_charge.return_value = True
        
        coop = Coop(api_key="test_api_key")
        result = coop.charge_proxy_key("encrypted_key", 100.0, "Test charge")
        
        assert result is True
        mock_add_charge.assert_called_once_with("encrypted_key", 100.0, "Test charge")
        
    @patch.object(ProxyKeyTracker, 'get_charge_history')
    def test_get_charge_history_integration(self, mock_get_history):
        """Test charge history retrieval through Coop."""
        mock_history = [
            ChargeRecord(
                proxy_key_hash="hash123",
                charge_amount=100.0,
                charge_date=datetime.now(timezone.utc),
                description="Test charge"
            )
        ]
        mock_get_history.return_value = mock_history
        
        coop = Coop(api_key="test_api_key")
        result = coop.get_proxy_key_charge_history("encrypted_key", limit=10)
        
        assert result == mock_history
        mock_get_history.assert_called_once_with("encrypted_key", 10)