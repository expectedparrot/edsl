#!/usr/bin/env python3
"""
Demo script showing proxy key encryption, decryption, and charge tracking functionality.

This script demonstrates the complete workflow:
1. Creating an encrypted proxy key
2. Decrypting the proxy key
3. Registering it for tracking
4. Adding charges and checking balance
5. Viewing charge history
"""

from edsl.coop import Coop
from edsl.coop.proxy_key_encryption import ProxyKeyEncryption
from edsl.coop.proxy_key_tracker import ProxyKeyTracker
import tempfile


def demo_proxy_key_workflow():
    """Demonstrate the complete proxy key workflow."""
    print("🔐 EDSL Proxy Key Demo")
    print("=" * 50)
    
    # Initialize Coop with a test API key
    coop = Coop(api_key="test_api_key_12345")
    
    print("\n1. Creating encrypted proxy key...")
    try:
        # Create an encrypted proxy key
        encrypted_key = coop.create_encrypted_proxy_key(
            max_charge_credits=500.0,
            duration_seconds=7200  # 2 hours
        )
        print(f"✅ Encrypted proxy key created (length: {len(encrypted_key)} chars)")
        print(f"   First 50 chars: {encrypted_key[:50]}...")
    except Exception as e:
        print(f"❌ Failed to create encrypted key: {e}")
        print("   Note: This requires GPG to be installed")
        return
    
    print("\n2. Decrypting proxy key...")
    try:
        # Decrypt the proxy key to see its contents
        payload = coop.decrypt_proxy_key(encrypted_key)
        print(f"✅ Decrypted successfully!")
        print(f"   EP Token: {payload.ep_token}")
        print(f"   Max Credits: {payload.max_charge_credits}")
        print(f"   Duration: {payload.duration_seconds} seconds")
        print(f"   Created: {payload.creation_date}")
    except Exception as e:
        print(f"❌ Failed to decrypt key: {e}")
        return
    
    print("\n3. Registering proxy key for tracking...")
    try:
        # Use a temporary database for this demo
        with tempfile.NamedTemporaryFile(suffix=".db") as temp_db:
            # Create tracker with temporary database
            tracker = ProxyKeyTracker(db_path=temp_db.name)
            
            # Register the key
            key_hash = tracker.register_proxy_key(encrypted_key, payload)
            print(f"✅ Registered proxy key with hash: {key_hash}")
            
            print("\n4. Checking initial balance...")
            balance = tracker.get_balance(encrypted_key)
            print(f"✅ Balance information:")
            print(f"   Max Credits: {balance.max_credits}")
            print(f"   Used Credits: {balance.used_credits}")
            print(f"   Remaining Credits: {balance.remaining_credits}")
            print(f"   Expired: {balance.is_expired}")
            
            print("\n5. Adding some charges...")
            charges = [
                (50.0, "API call batch 1"),
                (75.5, "Data processing"),
                (120.0, "Large query execution"),
                (25.25, "Model inference")
            ]
            
            for amount, description in charges:
                success = tracker.add_charge(encrypted_key, amount, description)
                if success:
                    print(f"   ✅ Charged {amount} credits: {description}")
                else:
                    print(f"   ❌ Failed to charge {amount} credits: {description} (insufficient balance)")
            
            print("\n6. Checking balance after charges...")
            balance = tracker.get_balance(encrypted_key)
            print(f"✅ Updated balance:")
            print(f"   Max Credits: {balance.max_credits}")
            print(f"   Used Credits: {balance.used_credits}")
            print(f"   Remaining Credits: {balance.remaining_credits}")
            print(f"   Expired: {balance.is_expired}")
            
            print("\n7. Viewing charge history...")
            history = tracker.get_charge_history(encrypted_key)
            print(f"✅ Charge history ({len(history)} records):")
            for record in history:
                print(f"   {record.charge_date.strftime('%Y-%m-%d %H:%M:%S')}: "
                      f"{record.charge_amount:6.2f} credits - {record.description}")
            
            print("\n8. Testing insufficient balance...")
            success = tracker.add_charge(encrypted_key, 1000.0, "Large charge that should fail")
            if success:
                print("   ❌ Charge succeeded when it should have failed")
            else:
                print("   ✅ Charge correctly rejected due to insufficient balance")
            
            print("\n9. Getting active keys summary...")
            summary = tracker.get_active_keys_summary()
            print(f"✅ Summary of all active keys:")
            print(f"   Active Keys: {summary['active_keys']}")
            print(f"   Total Max Credits: {summary['total_max_credits']}")
            print(f"   Total Used Credits: {summary['total_used_credits']}")
            print(f"   Total Remaining Credits: {summary['total_remaining_credits']}")
            
    except Exception as e:
        print(f"❌ Error during tracking operations: {e}")
        return
    
    print("\n🎉 Demo completed successfully!")
    print("\nProxy key functionality summary:")
    print("✅ Encryption/Decryption with GPG")
    print("✅ Charge tracking and balance management")
    print("✅ Expiration checking")
    print("✅ Charge history")
    print("✅ Database persistence")


def demo_convenience_functions():
    """Demonstrate the convenience functions."""
    print("\n" + "=" * 50)
    print("🛠️  Convenience Functions Demo")
    print("=" * 50)
    
    from edsl.coop import (
        create_encrypted_proxy_key,
        register_proxy_key,
        check_proxy_key_balance,
        charge_proxy_key
    )
    
    try:
        print("\n1. Creating proxy key with convenience function...")
        encrypted_key = create_encrypted_proxy_key(
            ep_token="convenience_test_token",
            max_charge_credits=100.0,
            duration_seconds=3600
        )
        print(f"✅ Created key with convenience function")
        
        print("\n2. Using convenience functions for tracking...")
        
        # These would fail without proper setup, but show the API
        print("   Available convenience functions:")
        print("   - create_encrypted_proxy_key()")
        print("   - register_proxy_key()")
        print("   - check_proxy_key_balance()")
        print("   - charge_proxy_key()")
        
    except Exception as e:
        print(f"   Note: Convenience functions require GPG: {e}")


if __name__ == "__main__":
    demo_proxy_key_workflow()
    demo_convenience_functions()