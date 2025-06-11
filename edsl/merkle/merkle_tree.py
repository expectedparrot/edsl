import hashlib
from typing import List, Optional, Any, Union, Dict


class MerkleTree:
    def __init__(self):
        self._elements: List[Any] = []
        self._tree: List[List[str]] = []
        self._root: Optional[str] = None
        
    def _hash_element(self, element: Any) -> str:
        if isinstance(element, str):
            data = element.encode('utf-8')
        elif isinstance(element, bytes):
            data = element
        else:
            data = str(element).encode('utf-8')
        return hashlib.sha256(data).hexdigest()
    
    def _hash_pair(self, left: str, right: str) -> str:
        combined = left + right
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()
    
    def add_element(self, element: Any) -> None:
        if element is None:
            raise ValueError("Cannot add None element to Merkle tree")
        self._elements.append(element)
        self._root = None
        
    def _build_tree(self) -> None:
        if not self._elements:
            self._tree = []
            self._root = None
            return
            
        current_level = [self._hash_element(element) for element in self._elements]
        self._tree = [current_level[:]]
        
        while len(current_level) > 1:
            next_level = []
            
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                if i + 1 < len(current_level):
                    right = current_level[i + 1]
                else:
                    right = left
                next_level.append(self._hash_pair(left, right))
            
            current_level = next_level
            self._tree.append(current_level[:])
        
        self._root = current_level[0] if current_level else None
    
    def get_root(self) -> Optional[str]:
        if self._root is None and self._elements:
            self._build_tree()
        return self._root
    
    def get_elements(self) -> List[Any]:
        return self._elements[:]
    
    def __len__(self) -> int:
        return len(self._elements)
    
    def __bool__(self) -> bool:
        return len(self._elements) > 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "elements": self._elements,
            "root": self.get_root()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MerkleTree":
        tree = cls()
        for element in data.get("elements", []):
            tree.add_element(element)
        return tree
    
    def contains(self, element: Any) -> bool:
        element_hash = self._hash_element(element)
        if not self._tree:
            self._build_tree()
        
        if not self._tree:
            return False
            
        return element_hash in self._tree[0]
    
    def get_proof(self, element: Any) -> List[str]:
        element_hash = self._hash_element(element)
        if not self._tree:
            self._build_tree()
        
        if not self._tree or element_hash not in self._tree[0]:
            return []
        
        proof = []
        element_index = self._tree[0].index(element_hash)
        
        for level in self._tree[:-1]:
            if element_index % 2 == 0:
                if element_index + 1 < len(level):
                    proof.append(level[element_index + 1])
                else:
                    proof.append(level[element_index])
            else:
                proof.append(level[element_index - 1])
            element_index //= 2
        
        return proof
    
    def verify_proof(self, element: Any, proof: List[str]) -> bool:
        element_hash = self._hash_element(element)
        current_hash = element_hash
        
        for sibling_hash in proof:
            if current_hash <= sibling_hash:
                current_hash = self._hash_pair(current_hash, sibling_hash)
            else:
                current_hash = self._hash_pair(sibling_hash, current_hash)
        
        return current_hash == self.get_root()
    
    def visualize(self, hash_length: int = 6) -> str:
        if not self._tree:
            self._build_tree()
        
        if not self._tree:
            return "Empty tree"
        
        visualization = []
        max_width = len(self._tree[0]) * 2 - 1
        
        for level_idx, level in enumerate(reversed(self._tree)):
            level_str = ""
            nodes_in_level = len(level)
            spacing = max_width // (nodes_in_level * 2) if nodes_in_level > 0 else 0
            
            for i, hash_val in enumerate(level):
                short_hash = hash_val[-hash_length:]
                if i > 0:
                    level_str += "  "
                level_str += short_hash
            
            level_label = f"Level {len(self._tree) - level_idx - 1}: "
            visualization.append(level_label + level_str)
        
        return "\n".join(visualization)
    
    def print_tree(self, hash_length: int = 6) -> None:
        print(self.visualize(hash_length))