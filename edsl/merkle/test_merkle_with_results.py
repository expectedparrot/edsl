#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from edsl.results import Results
from merkle_tree import MerkleTree


def test_merkle_with_results():
    print("=== Testing Merkle Tree with EDSL Results ===\n")
    
    # Create example results
    print("1. Creating EDSL Results examples...")
    results = Results.example()
    print(f"   Created Results with {len(results)} Result objects")
    
    # Create multiple results for testing
    results_list = []
    for i in range(5):
        r = Results.example()
        results_list.append(r)
    print(f"   Created {len(results_list)} different Results objects\n")
    
    # Create Merkle tree and add results
    print("2. Building Merkle tree...")
    merkle = MerkleTree()
    
    for i, result in enumerate(results_list):
        merkle.add_element(result)
        print(f"   Added Results object {i+1}")
    
    print(f"   Merkle tree contains {len(merkle)} elements")
    print(f"   Merkle root: {merkle.get_root()[:16]}...\n")
    
    # Test membership of original results
    print("3. Testing membership of original Results objects...")
    for i, result in enumerate(results_list):
        is_member = merkle.contains(result)
        print(f"   Results {i+1} is member: {is_member}")
        
        if is_member:
            proof = merkle.get_proof(result)
            verified = merkle.verify_proof(result, proof)
            print(f"   Proof verification: {verified}")
    print()
    
    # Test with different object that wasn't added to tree
    print("4. Testing with object not in tree...")
    print(f"   Original result hash: {merkle._hash_element(results_list[0])[:16]}...")
    
    # Create a simple different object that definitely wasn't added
    different_object = "This is a different object not in the tree"
    fake_results = {"fake": "results", "data": [1, 2, 3]}
    
    print(f"   Different string hash: {merkle._hash_element(different_object)[:16]}...")
    print(f"   Fake results hash: {merkle._hash_element(fake_results)[:16]}...")
    
    is_member_original = merkle.contains(results_list[0])
    is_member_different_str = merkle.contains(different_object)
    is_member_fake = merkle.contains(fake_results)
    
    print(f"   Original Results is member: {is_member_original}")
    print(f"   Different string is member: {is_member_different_str}")
    print(f"   Fake results dict is member: {is_member_fake}")
    
    if not is_member_different_str and not is_member_fake:
        print("   ✓ Successfully demonstrated non-membership of objects not in tree")
    else:
        print("   ⚠ Unexpected membership result")
    print()
    
    # Test serialization
    print("5. Testing serialization...")
    tree_dict = merkle.to_dict()
    print(f"   Serialized tree with {len(tree_dict['elements'])} elements")
    print(f"   Serialized root: {tree_dict['root'][:16]}...")
    
    # Deserialize and verify
    restored_tree = MerkleTree.from_dict(tree_dict)
    print(f"   Restored tree with {len(restored_tree)} elements")
    print(f"   Restored root: {restored_tree.get_root()[:16]}...")
    print(f"   Roots match: {tree_dict['root'] == restored_tree.get_root()}")
    
    # Verify membership still works after deserialization
    restored_member_check = restored_tree.contains(results_list[0])
    print(f"   Membership check after restore: {restored_member_check}")
    print()
    
    # Test visualization
    print("6. Testing tree visualization...")
    print("   Tree structure:")
    merkle.print_tree(hash_length=8)
    print()
    
    # Test with different hash length
    print("   Tree with shorter hashes (4 chars):")
    merkle.print_tree(hash_length=4)
    print()
    
    print("=== Test Complete ===")


if __name__ == "__main__":
    test_merkle_with_results()