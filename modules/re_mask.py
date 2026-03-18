#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Re-Masking Module v2.3.0
Multi-pass masking with chain tracking for data_masking.py

Provides:
    - MappingChain: tracks mappings across multiple re-mask passes
    - ReMasker: applies re-masking using a callable mask_function
    - ChainUnmasker: reverses multi-pass masking back to any version

Chain JSON format:
    {
        "version": "2.3.0",
        "chain_id": "<sha256_hash[:12]>",
        "chain_version": 2,
        "created_at": "ISO-8601",
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

import argparse
import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

__version__ = "2.3.0"

# Standard mapping categories used by data_masking.py
MAPPING_CATEGORIES = [
    "ipn", "passport_id", "military_id", "surname", "name",
    "military_unit", "order_number", "order_number_with_letters",
    "br_number", "br_number_slash", "br_number_complex",
    "rank", "brigade_number", "date", "patronymic"
]


def make_empty_masking_dict(version: str = "2.3.0") -> Dict:
    """Create a fresh empty masking dict with all required category keys.

    Args:
        version: Version string to embed in the masking dict.
    """
    return {
        "version": version,
        "timestamp": datetime.now().isoformat(),
        "statistics": {},
        "mappings": {k: {} for k in MAPPING_CATEGORIES},
        "instance_tracking": {}
    }


def _generate_chain_id() -> str:
    """Generate a unique chain ID from current datetime SHA256 hash[:12].

    Returns a 12-character hex string from the SHA256 of the ISO timestamp.
    """
    now_str = datetime.now().isoformat()
    return hashlib.sha256(now_str.encode("utf-8")).hexdigest()[:12]


# ============================================================================
# MappingChain
# ============================================================================

class MappingChain:
    """Tracks mappings across multiple re-mask passes.

    Each pass stores its own independent masking_dict so that unmasking can
    be performed in reverse order to recover any intermediate version.
    """

    def __init__(self, chain_id: Optional[str] = None):
        """Initialise a new MappingChain.

        Args:
            chain_id: Optional explicit chain ID. When None, generated
                from datetime SHA256 hash[:12].
        """
        self._chain_id: str = chain_id if chain_id else _generate_chain_id()
        self._created_at: str = datetime.now().isoformat()
        self._passes: List[Dict] = []
        self._current_pass: int = 0

    @property
    def chain_id(self) -> str:
        """Unique chain identifier."""
        return self._chain_id

    @property
    def created_at(self) -> str:
        """ISO-8601 creation timestamp."""
        return self._created_at

    @property
    def passes(self) -> List[Dict]:
        """Ordered list of pass records."""
        return self._passes

    @passes.setter
    def passes(self, value: List[Dict]) -> None:
        self._passes = value

    @property
    def current_pass(self) -> int:
        """Number of passes added so far."""
        return self._current_pass

    @current_pass.setter
    def current_pass(self, value: int) -> None:
        self._current_pass = value

    def add_pass(self, masking_dict: Dict) -> int:
        """Add a completed pass's masking dict to the chain.

        Args:
            masking_dict: The masking dict produced by one masking pass.
                Expected keys: 'version', 'mappings', 'instance_tracking',
                'statistics'.

        Returns:
            The pass number (1-indexed) that was just added.
        """
        self._current_pass += 1
        pass_entry = {
            "pass": self._current_pass,
            "version": masking_dict.get("version", __version__),
            "mappings": copy.deepcopy(masking_dict.get("mappings", {})),
            "instance_tracking": copy.deepcopy(
                masking_dict.get("instance_tracking", {})
            ),
            "statistics": copy.deepcopy(masking_dict.get("statistics", {})),
        }
        self._passes.append(pass_entry)
        return self._current_pass

    def get_pass(self, pass_number: int) -> Optional[Dict]:
        """Get a specific pass's mapping data (1-indexed).

        Args:
            pass_number: The 1-based index of the desired pass.

        Returns:
            The pass record dict, or None if pass_number is out of range.
        """
        for p in self._passes:
            if p.get("pass") == pass_number:
                return p
        return None

    def get_chain_mapping(self, from_pass: int, to_pass: int) -> Dict:
        """Build a composite mapping from from_pass to to_pass.

        If to_pass > from_pass the forward chain is used; otherwise
        the reverse chain is built for unmasking.

        Args:
            from_pass: Starting pass number (1-indexed).
            to_pass:   Target pass number (1-indexed).

        Returns:
            A dict mapping tokens at from_pass to their equivalents at
            to_pass.  Returns an empty dict when from_pass == to_pass.
        """
        if from_pass == to_pass:
            return {}
        if from_pass < to_pass:
            return self._build_forward_chain(from_pass, to_pass)
        return self._build_reverse_chain(from_pass, to_pass)

    def _build_forward_chain(self, from_pass: int, to_pass: int) -> Dict:
        """Compose forward mappings from from_pass to to_pass.
        Chains original->masked relationships through intermediate passes."""
        # Seed with the from_pass mapping
        combined: Dict[str, str] = {}
        seed_data = self.get_pass(from_pass)
        if seed_data is not None:
            for _cat, pairs in seed_data.get("mappings", {}).items():
                if isinstance(pairs, dict):
                    combined.update(pairs)
        # Chain through subsequent passes
        for step in range(from_pass + 1, to_pass + 1):
            step_data = self.get_pass(step)
            if step_data is None:
                continue
            step_flat: Dict[str, str] = {}
            for _cat, pairs in step_data.get("mappings", {}).items():
                if isinstance(pairs, dict):
                    step_flat.update(pairs)
            new_combined: Dict[str, str] = {}
            for orig, intermediate in combined.items():
                if intermediate in step_flat:
                    new_combined[orig] = step_flat[intermediate]
                else:
                    new_combined[orig] = intermediate
            existing_vals = set(combined.values())
            for k, v in step_flat.items():
                if k not in existing_vals:
                    new_combined[k] = v
            combined = new_combined
        return combined

    def _build_reverse_chain(self, from_pass: int, to_pass: int) -> Dict:
        """Compose reverse mappings from from_pass back to to_pass.
        Inverts each pass mapping and walks backwards.
        """
        combined: Dict[str, str] = {}
        for step in range(from_pass, to_pass, -1):
            step_data = self.get_pass(step)
            if step_data is None:
                continue
            step_inv: Dict[str, str] = {}
            for _cat, pairs in step_data.get("mappings", {}).items():
                if isinstance(pairs, dict):
                    for orig, masked in pairs.items():
                        step_inv[masked] = orig
            if not combined:
                combined = dict(step_inv)
            else:
                new_combined: Dict[str, str] = {}
                for k, intermediate in combined.items():
                    new_combined[k] = step_inv.get(intermediate, intermediate)
                existing_vals = set(combined.values())
                for k, v in step_inv.items():
                    if k not in existing_vals:
                        new_combined[k] = v
                combined = new_combined
        return combined

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the chain to a plain dict suitable for JSON output."""
        return {
            "version": __version__,
            "chain_id": self._chain_id,
            "chain_version": 2,
            "created_at": self._created_at,
            "total_passes": len(self._passes),
            "timestamp": datetime.now().isoformat(),
            "passes": copy.deepcopy(self._passes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MappingChain":
        """Reconstruct a MappingChain from a dict (e.g. loaded from JSON).
        """
        chain_id = data.get("chain_id", _generate_chain_id())
        chain = cls(chain_id=chain_id)
        chain._created_at = data.get("created_at", chain._created_at)
        chain._passes = data.get("passes", [])
        chain._current_pass = len(chain._passes)
        return chain

    def save(self, path: Any) -> None:
        """Save the chain to a JSON file.

        Args:
            path: Filesystem path (str or Path) for the output file.
        """
        path = Path(path)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: Any) -> "MappingChain":
        """Load a chain from a JSON file.

        Args:
            path: Filesystem path (str or Path) to a chain JSON file.

        Returns:
            A MappingChain instance populated from the file.
        """
        path = Path(path)
        with open(path, "r", encoding="utf-8") as fh:
            chain_data = json.load(fh)
        return cls.from_dict(chain_data)

    @staticmethod
    def is_chain_file(data: Dict) -> bool:
        """Check whether data represents a chain (has a 'passes' key).

        Args:
            data: A dict loaded from a JSON mapping file.

        Returns:
            True if data looks like a chain file, False otherwise.
        """
        return "passes" in data and isinstance(data["passes"], list)


# ============================================================================
# ReMasker
# ============================================================================

class ReMasker:
    """Applies re-masking using a user-supplied mask function.

    The mask_function signature:
        Callable[[str, Dict, Dict], Tuple[str, Dict, Dict]]
        (text, masking_dict, instance_counters) -> (text, masking_dict, instance_counters)
    """

    def __init__(
        self,
        mask_function: Callable[..., Tuple[str, Dict, Dict]],
        chain: Optional[MappingChain] = None,
    ):
        """Initialise the ReMasker.

        Args:
            mask_function: Callable (text, mapping, counters) -> (text, mapping, counters).
            chain: Optional pre-existing MappingChain. Created when None.
        """
        self.mask_function = mask_function
        self.chain = chain if chain is not None else MappingChain()

    def mask_once(
        self,
        text: str,
        masking_dict: Optional[Dict] = None,
        instance_counters: Optional[Dict] = None,
    ) -> Tuple[str, Dict, Dict]:
        """Apply a single masking pass and record it in the chain.

        Returns:
            Tuple of (masked_text, masking_dict, instance_counters).
        """
        if masking_dict is None:
            masking_dict = make_empty_masking_dict()
        if instance_counters is None:
            instance_counters = {}
        result_text, result_dict, result_counters = self.mask_function(
            text, masking_dict, instance_counters
        )
        result_dict["instance_tracking"] = result_counters
        self.chain.add_pass(result_dict)
        return result_text, result_dict, result_counters

    def mask_multiple(
        self, text: str, n_passes: int = 2
    ) -> Tuple[str, MappingChain]:
        """Apply n_passes consecutive masking passes.

        Returns:
            Tuple of (final_masked_text, mapping_chain).
        """
        current_text = text
        for _ in range(n_passes):
            current_text, _md, _ic = self.mask_once(current_text)
        return current_text, self.chain

    def get_chain(self) -> MappingChain:
        """Return the MappingChain recording all passes."""
        return self.chain


# ============================================================================
# ChainUnmasker
# ============================================================================

class ChainUnmasker:
    """Reverses multi-pass masking recorded in a MappingChain.

    Can undo one step, all steps, or jump to any intermediate version.
    """

    def __init__(self, chain: MappingChain):
        """Initialise the ChainUnmasker.

        Args:
            chain: A MappingChain containing one or more passes.
        """
        self.chain = chain

    def unmask_to_version(self, text: str, target_version: int) -> str:
        """Unmask text back to the state at target_version.

        Args:
            text: Text after all passes in the chain.
            target_version: 1-based pass to revert to (0 = original).

        Returns:
            Text as it existed at target_version.
        """
        if target_version < 0:
            target_version = 0
        total = self.chain.current_pass
        if target_version >= total:
            return text
        current_text = text
        for step in range(total, target_version, -1):
            current_text = self._apply_reverse_pass(current_text, step)
        return current_text

    def unmask_one_step(self, text: str) -> str:
        """Unmask exactly one pass (the most recent one)."""
        total = self.chain.current_pass
        if total < 1:
            return text
        return self._apply_reverse_pass(text, total)

    def unmask_all(self, text: str) -> str:
        """Unmask all passes, returning the original pre-masking text."""
        return self.unmask_to_version(text, 0)

    def _apply_reverse_pass(self, text: str, pass_number: int) -> str:
        """Reverse a single pass by substituting masked tokens back.

        Longer tokens are replaced first to prevent partial matches.
        """
        pass_data = self.chain.get_pass(pass_number)
        if pass_data is None:
            return text
        mappings = pass_data.get("mappings", {})
        inverted: Dict[str, str] = {}
        for _cat, pairs in mappings.items():
            if isinstance(pairs, dict):
                for orig, masked in pairs.items():
                    inverted[masked] = orig
        # Sort by length descending to avoid partial replacements
        for masked_token in sorted(inverted, key=len, reverse=True):
            text = text.replace(masked_token, inverted[masked_token])
        return text


# ============================================================================
# Convenience functions
# ============================================================================

def create_remasker(
    mask_function: Callable[..., Tuple[str, Dict, Dict]],
    chain: Optional[MappingChain] = None,
) -> ReMasker:
    """Create a ReMasker with the given mask_function."""
    return ReMasker(mask_function=mask_function, chain=chain)


def load_chain(path: Any) -> MappingChain:
    """Load a MappingChain from a JSON file."""
    return MappingChain.load(path)


def get_chain_info(chain: MappingChain) -> Dict[str, Any]:
    """Return a human-readable summary of a MappingChain."""
    summaries: List[Dict[str, Any]] = []
    for p in chain.passes:
        mappings = p.get("mappings", {})
        total_mappings = sum(
            len(v) for v in mappings.values() if isinstance(v, dict)
        )
        summaries.append({
            "pass": p.get("pass"),
            "version": p.get("version", "unknown"),
            "total_mappings": total_mappings,
            "categories_used": [
                cat for cat, pairs in mappings.items()
                if isinstance(pairs, dict) and len(pairs) > 0
            ],
        })
    return {
        "chain_id": chain.chain_id,
        "created_at": chain.created_at,
        "total_passes": chain.current_pass,
        "version": __version__,
        "pass_summaries": summaries,
    }


# ============================================================================
# CLI argument helpers
# ============================================================================

def add_remask_args(parser: argparse.ArgumentParser) -> None:
    """Add re-masking related arguments to an argparse parser.

    Adds: --re-mask N, --chain-out PATH, --chain-id ID
    """
    group = parser.add_argument_group("Re-masking options")
    group.add_argument(
        "--re-mask",
        type=int,
        default=0,
        metavar="N",
        help="Number of additional masking passes (0 = single pass, default).",
    )
    group.add_argument(
        "--chain-out",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to save the mapping chain JSON file.",
    )
    group.add_argument(
        "--chain-id",
        type=str,
        default=None,
        metavar="ID",
        help="Explicit chain ID (auto-generated when omitted).",
    )


def add_unmask_version_args(parser: argparse.ArgumentParser) -> None:
    """Add chain-unmask related arguments to an argparse parser.

    Adds: --chain-in PATH, --target-version N, --unmask-one-step
    """
    group = parser.add_argument_group("Chain unmask options")
    group.add_argument(
        "--chain-in",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to a mapping chain JSON file.",
    )
    group.add_argument(
        "--target-version",
        type=int,
        default=0,
        metavar="N",
        help="Pass version to unmask to (0 = original text, default).",
    )
    group.add_argument(
        "--unmask-one-step",
        action="store_true",
        default=False,
        help="Undo only the most recent masking pass.",
    )
