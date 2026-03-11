#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Re-Mask Module v2.2.15
Multi-pass masking with chain tracking for data_masking.py

Provides:
    - MappingChain: tracks mappings across multiple re-mask passes
    - ReMasker: applies re-masking using previous mapping as context

Chain JSON format:
    {
        "version": "2.2.15",
        "chain_version": 1,
        "total_passes": N,
        "passes": [
            {"pass": 1, "version": "...", "mappings": {...}, "instance_tracking": {...}},
            {"pass": 2, "version": "...", "mappings": {...}, "instance_tracking": {...}},
            ...
        ]
    }

Author: Vladyslav V. Prodan
Contact: github.com/click0
License: BSD 3-Clause
Year: 2025
"""

import json
import copy
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any


# Standard mapping categories used by data_masking.py
MAPPING_CATEGORIES = [
    "ipn", "passport_id", "military_id", "surname", "name",
    "military_unit", "order_number", "order_number_with_letters",
    "br_number", "br_number_slash", "br_number_complex",
    "rank", "brigade_number", "date", "patronymic"
]


def make_empty_masking_dict(version: str = "2.2.15") -> Dict:
    """Create a fresh empty masking dict with all required category keys."""
    return {
        "version": version,
        "timestamp": datetime.now().isoformat(),
        "statistics": {},
        "mappings": {k: {} for k in MAPPING_CATEGORIES},
        "instance_tracking": {}
    }


class MappingChain:
    """Tracks mapping across multiple re-mask passes.

    Each pass stores its own independent masking_dict so that
    unmasking can be performed in reverse order to recover the original text.
    """

    def __init__(self):
        self.current_pass: int = 0
        self.passes: List[Dict] = []

    def add_pass(self, masking_dict: Dict) -> None:
        """Add a completed pass's masking dict to the chain."""
        self.current_pass += 1
        pass_entry = {
            "pass": self.current_pass,
            "version": masking_dict.get("version", "2.2.15"),
            "mappings": copy.deepcopy(masking_dict.get("mappings", {})),
            "instance_tracking": copy.deepcopy(masking_dict.get("instance_tracking", {})),
            "statistics": copy.deepcopy(masking_dict.get("statistics", {}))
        }
        self.passes.append(pass_entry)

    def save(self, path) -> None:
        """Save the chain to a JSON file."""
        chain_data = {
            "version": self.passes[0]["version"] if self.passes else "2.2.15",
            "chain_version": 1,
            "total_passes": len(self.passes),
            "timestamp": datetime.now().isoformat(),
            "passes": self.passes
        }
        path = Path(path)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(chain_data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path) -> "MappingChain":
        """Load a chain from a JSON file."""
        path = Path(path)
        with open(path, 'r', encoding='utf-8') as f:
            chain_data = json.load(f)

        chain = cls()
        chain.passes = chain_data.get("passes", [])
        chain.current_pass = len(chain.passes)
        return chain

    @staticmethod
    def is_chain_file(data: Dict) -> bool:
        """Check if a mapping dict represents a chain (has 'passes' key)."""
        return "passes" in data and isinstance(data["passes"], list)

    def get_pass(self, pass_number: int) -> Optional[Dict]:
        """Get a specific pass's mapping data (1-indexed)."""
        for p in self.passes:
            if p.get("pass") == pass_number:
                return p
        return None


class ReMasker:
    """Applies re-masking using previous mapping as context.

    Takes an existing mapping (from a previous masking pass) and provides
    methods to apply additional masking passes while tracking the chain.
    """

    def __init__(self, original_mapping: Dict):
        self.original_mapping = copy.deepcopy(original_mapping)
        self.chain = MappingChain()
        # Add the original mapping as pass 1
        if original_mapping.get("mappings"):
            self.chain.add_pass(original_mapping)

    def remask(self, text: str, mask_function, masking_dict: Dict,
               instance_counters: Dict) -> str:
        """Apply one re-masking pass.

        Args:
            text: Text to re-mask (already masked from previous pass)
            mask_function: The masking function (mask_text_context_aware)
            masking_dict: Fresh masking dict for this pass
            instance_counters: Fresh instance counters for this pass

        Returns:
            Re-masked text
        """
        result = mask_function(text, masking_dict, instance_counters)
        masking_dict["instance_tracking"] = instance_counters
        self.chain.add_pass(masking_dict)
        return result

    def get_chain(self) -> MappingChain:
        """Get the mapping chain."""
        return self.chain
