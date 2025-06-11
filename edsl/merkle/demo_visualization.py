#!/usr/bin/env python3

from merkle_tree import MerkleTree

def demo_visualization():
    print("=== Merkle Tree Visualization Demo ===\n")
    
    # Demo 1: Small tree with 3 elements
    print("1. Tree with 3 elements:")
    tree1 = MerkleTree()
    tree1.add_element("Alice")
    tree1.add_element("Bob") 
    tree1.add_element("Charlie")
    tree1.print_tree(hash_length=8)
    print()
    
    # Demo 2: Tree with 7 elements
    print("2. Tree with 7 elements:")
    tree2 = MerkleTree()
    for name in ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace"]:
        tree2.add_element(name)
    tree2.print_tree(hash_length=6)
    print()
    
    # Demo 3: Tree with single element
    print("3. Tree with single element:")
    tree3 = MerkleTree()
    tree3.add_element("Lonely Node")
    tree3.print_tree()
    print()
    
    # Demo 4: Empty tree
    print("4. Empty tree:")
    tree4 = MerkleTree()
    print(tree4.visualize())
    print()

if __name__ == "__main__":
    demo_visualization()