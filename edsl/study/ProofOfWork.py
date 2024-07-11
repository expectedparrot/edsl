import hashlib
import time
from typing import Any, Dict, List, Optional


class ProofOfWork:
    def __init__(
        self,
        input_data: Optional[Any] = None,
        proof: Optional[Dict[int, List[Dict[str, Any]]]] = None,
    ):
        self.input_data = input_data
        self.proof = proof or {}

    def add_input_data(self, input_data: Any) -> None:
        self.input_data = input_data

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_data": self.input_data,
            "proof": self.proof,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProofOfWork":
        return cls(data["input_data"], data["proof"])

    def __repr__(self) -> str:
        return f"ProofOfWork(input_data={self.input_data}, proof={self.proof})"

    def to_hash(self, nonce: int) -> str:
        """
        Hash the input data combined with the nonce.

        Returns:
        str: The resulting hash.
        """
        hash_input = self.input_data + str(nonce)
        return hashlib.md5(hash_input.encode()).hexdigest()

    def verify_work(self) -> bool:
        for difficulty in self.proof:
            for proof in self.proof[difficulty]:
                nonce = proof["nonce"]
                hash_result = self.to_hash(nonce)
                prefix = "0" * difficulty
                if not hash_result.startswith(prefix):
                    return False
                if hash_result != proof["hash"]:
                    return False
        return True

    def add_proof(self, difficulty: int, starting_nonce: Optional[int] = None) -> None:
        """
        Find a nonce that results in a hash with `difficulty` number of leading zeros.

        Returns:
        int, str: The nonce that solves the proof of work and the resulting hash.
        """
        # Convert the difficulty into a string of zeros for comparison
        prefix = "0" * difficulty
        if not starting_nonce:
            import random

            starting_nonce = random.randint(0, 1000000)
        nonce = starting_nonce
        start = time.time()
        while True:
            # Combine the input data with the nonce and hash it
            hash_result = self.to_hash(nonce)

            # Check if the hash meets the difficulty requirement
            if hash_result.startswith(prefix):
                cycles = nonce - starting_nonce
                end = time.time()
                if difficulty in self.proof:
                    self.proof[difficulty].append(
                        {
                            "nonce": nonce,
                            "hash": hash_result,
                            "time": end - start,
                            "cycles": cycles,
                        }
                    )
                else:
                    self.proof[difficulty] = [
                        {
                            "nonce": nonce,
                            "hash": hash_result,
                            "time": end - start,
                            "cycles": cycles,
                        }
                    ]
                return

            nonce += 1


if __name__ == "__main__":
    from edsl.study import ProofOfWork

    p = ProofOfWork("hello world")
    p.add_proof(3)
    print(p)
    p.add_proof(6)
    print(p)

    # Takes about a minute to run
    p.add_proof(7)
    print(p)

    ok = p.verify_work()
    print(ok)
