import hashlib
import json
import os
from datetime import datetime


def current_timestamp():
    """Return a readable timestamp for medicine and block records."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Block:
    """A single block in the custom blockchain."""

    def __init__(
        self,
        index,
        previous_hash,
        timestamp,
        transactions=None,
        merkle_root="",
        nonce=0,
        hash_value="",
    ):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.transactions = transactions or []
        self.merkle_root = merkle_root or self.calculate_merkle_root()
        self.nonce = nonce
        self.hash = hash_value or self.calculate_hash()

    def calculate_merkle_root(self):
        """Build a Merkle root from the block transactions."""
        if not self.transactions:
            return hashlib.sha256("empty".encode()).hexdigest()

        hashes = [
            hashlib.sha256(json.dumps(tx, sort_keys=True).encode()).hexdigest()
            for tx in self.transactions
        ]

        while len(hashes) > 1:
            if len(hashes) % 2 != 0:
                hashes.append(hashes[-1])

            next_level = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i + 1]
                next_level.append(hashlib.sha256(combined.encode()).hexdigest())
            hashes = next_level

        return hashes[0]

    def calculate_hash(self):
        """Hash the block header using SHA256."""
        block_data = {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "merkle_root": self.merkle_root,
            "nonce": self.nonce,
        }
        encoded = json.dumps(block_data, sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()

    def mine_block(self, difficulty):
        """Run Proof-of-Work until the hash begins with the target zeros."""
        target = "0" * difficulty
        self.hash = self.calculate_hash()

        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.calculate_hash()

    def to_dict(self):
        """Convert the block into a JSON-friendly dictionary."""
        return {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "merkle_root": self.merkle_root,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data):
        """Rebuild a block from saved JSON data."""
        return cls(
            index=data["index"],
            previous_hash=data["previous_hash"],
            timestamp=data["timestamp"],
            transactions=data.get("transactions", []),
            merkle_root=data.get("merkle_root", ""),
            nonce=data.get("nonce", 0),
            hash_value=data.get("hash", ""),
        )


class MedicineBlockchain:
    """Custom blockchain for storing medicine authenticity records."""

    def __init__(self, difficulty=3, storage_path=None):
        self.difficulty = difficulty
        self.storage_path = storage_path
        self.chain = []
        self.pending_transactions = []

        if self.storage_path and os.path.exists(self.storage_path):
            self.load_data()
        else:
            self.create_genesis_block()
            self.save_data()

    def create_genesis_block(self):
        """Create the first block in the chain."""
        genesis = Block(
            index=0,
            previous_hash="0",
            timestamp=current_timestamp(),
            transactions=[],
        )
        genesis.mine_block(self.difficulty)
        self.chain = [genesis]

    def create_transaction(
        self,
        medicine_name,
        batch_id,
        manufacturer_name="",
        qr_code_file="",
        stage="Manufacturer",
        party_name="",
        from_party="",
        to_party="",
        notes="",
    ):
        """Create a new supply chain transaction."""
        registered_at = current_timestamp()
        resolved_party = (party_name or manufacturer_name or "").strip()
        raw_id = (
            f"{medicine_name}-{batch_id}-{stage}-{resolved_party}-{from_party}-{to_party}-{registered_at}".encode()
        )
        transaction_id = hashlib.sha256(raw_id).hexdigest()[:16]

        return {
            "transaction_id": transaction_id,
            "medicine_name": medicine_name,
            "batch_id": batch_id,
            "stage": stage,
            "party_name": resolved_party,
            "manufacturer_name": resolved_party if stage == "Manufacturer" else manufacturer_name,
            "from_party": from_party,
            "to_party": to_party,
            "notes": notes,
            "registered_at": registered_at,
            "qr_code_file": qr_code_file,
        }

    def add_transaction(self, transaction):
        """Add a transaction to the pending queue."""
        self.pending_transactions.append(transaction)
        self.save_data()

    def mine_pending_transactions(self):
        """
        Mine a block for all pending transactions.

        In this project we mine after each registration, so every medicine
        batch gets a clear traceable block.
        """
        if not self.pending_transactions:
            return None

        new_block = Block(
            index=len(self.chain),
            previous_hash=self.chain[-1].hash,
            timestamp=current_timestamp(),
            transactions=self.pending_transactions.copy(),
        )
        new_block.mine_block(self.difficulty)

        self.chain.append(new_block)
        self.pending_transactions = []
        self.save_data()
        return new_block

    def is_chain_valid(self):
        """Validate hashes, links, Merkle roots, and proof-of-work."""
        if not self.chain:
            return False

        target = "0" * self.difficulty

        for index, block in enumerate(self.chain):
            if block.hash != block.calculate_hash():
                return False

            if block.merkle_root != block.calculate_merkle_root():
                return False

            if not block.hash.startswith(target):
                return False

            if index == 0:
                if block.previous_hash != "0":
                    return False
            else:
                previous_block = self.chain[index - 1]
                if block.previous_hash != previous_block.hash:
                    return False

        return True

    def get_batch_history(self, batch_id):
        """Return all records that match a batch ID."""
        batch_key = batch_id.strip().lower()
        history = []

        for block in self.chain:
            for tx in block.transactions:
                if tx.get("batch_id", "").strip().lower() == batch_key:
                    history.append(
                        {
                            **tx,
                            "block_index": block.index,
                            "block_timestamp": block.timestamp,
                            "block_hash": block.hash,
                            "previous_hash": block.previous_hash,
                            "merkle_root": block.merkle_root,
                            "nonce": block.nonce,
                        }
                    )

        return history

    def verify_batch(self, batch_id):
        """Return whether a batch exists and its full history."""
        history = self.get_batch_history(batch_id)
        return bool(history), history

    def get_all_records(self):
        """Return all medicine registrations in the chain."""
        records = []

        for block in self.chain[1:]:
            for tx in block.transactions:
                records.append(
                    {
                        **tx,
                        "block_index": block.index,
                        "block_timestamp": block.timestamp,
                        "block_hash": block.hash,
                    }
                )

        records.sort(key=lambda item: item["block_index"], reverse=True)
        return records

    def get_unique_batch_count(self):
        """Count unique batch IDs stored in the chain."""
        return len(
            {
                record["batch_id"].strip().lower()
                for record in self.get_all_records()
            }
        )

    def get_chain_data(self):
        """Return the full chain as serializable dictionaries."""
        return [block.to_dict() for block in self.chain]

    def save_data(self):
        """Save the blockchain to disk."""
        if not self.storage_path:
            return

        directory = os.path.dirname(self.storage_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        data = {
            "difficulty": self.difficulty,
            "pending_transactions": self.pending_transactions,
            "chain": [block.to_dict() for block in self.chain],
        }

        with open(self.storage_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)

    def load_data(self):
        """Load blockchain data from disk."""
        try:
            with open(self.storage_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            self.difficulty = data.get("difficulty", self.difficulty)
            self.pending_transactions = data.get("pending_transactions", [])
            self.chain = [Block.from_dict(item) for item in data.get("chain", [])]

            if not self.chain:
                self.create_genesis_block()
                self.pending_transactions = []
                self.save_data()
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            self.pending_transactions = []
            self.create_genesis_block()
            self.save_data()
