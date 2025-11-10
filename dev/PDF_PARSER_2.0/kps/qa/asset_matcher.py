"""Asset matching algorithms for comparing source and output assets."""

import hashlib
from typing import Optional, List, Tuple, Dict
from pathlib import Path
from PIL import Image
import numpy as np

from kps.core import Asset, AssetType
from .qa_utils import (
    calculate_hash,
    load_image,
    bytes_to_image,
)
from .constants import (
    VISUAL_SIMILARITY_THRESHOLD,
    VISUAL_SIMILARITY_STRICT,
    COMPARISON_RESIZE,
    HIGH_RES_COMPARISON,
    HASH_MATCH_PRIORITY,
    VISUAL_MATCH_PRIORITY,
    CRITICAL_SIZE_THRESHOLD,
)


class AssetMatch:
    """Result of asset matching operation."""

    def __init__(
        self,
        source_asset: Asset,
        output_asset: Optional[dict],
        match_method: str,
        confidence: float,
        matched: bool,
    ):
        self.source_asset = source_asset
        self.output_asset = output_asset
        self.match_method = match_method  # "hash", "visual", "none"
        self.confidence = confidence  # 0.0-1.0
        self.matched = matched

    def __repr__(self) -> str:
        return (
            f"AssetMatch(asset_id={self.source_asset.asset_id}, "
            f"matched={self.matched}, method={self.match_method}, "
            f"confidence={self.confidence:.2f})"
        )


class AssetMatcher:
    """
    Match assets between source and output PDFs.

    Matching strategies:
    1. Exact hash match (SHA256) - highest priority
    2. Visual similarity - fallback for re-rendered assets
    3. Metadata match (size, position) - last resort
    """

    def __init__(
        self,
        visual_threshold: float = VISUAL_SIMILARITY_THRESHOLD,
        strict_mode: bool = False,
    ):
        """
        Initialize asset matcher.

        Args:
            visual_threshold: Minimum similarity for visual matching
            strict_mode: Use stricter thresholds for critical assets
        """
        self.visual_threshold = visual_threshold
        self.strict_mode = strict_mode
        self._match_cache: Dict[str, AssetMatch] = {}

    def find_match(
        self, source_asset: Asset, output_assets: List[dict]
    ) -> Optional[AssetMatch]:
        """
        Find matching asset in output.

        Tries multiple matching strategies:
        1. Exact hash match (SHA256)
        2. Visual similarity (for re-rendered assets)
        3. Metadata match (size, position)

        Args:
            source_asset: Asset from source PDF
            output_assets: List of extracted output assets

        Returns:
            AssetMatch if found, None otherwise
        """
        # Check cache first
        cache_key = source_asset.asset_id
        if cache_key in self._match_cache:
            return self._match_cache[cache_key]

        # Try hash match first (fastest and most accurate)
        hash_match = self._find_by_hash(source_asset, output_assets)
        if hash_match:
            match = AssetMatch(
                source_asset=source_asset,
                output_asset=hash_match,
                match_method="hash",
                confidence=1.0,
                matched=True,
            )
            self._match_cache[cache_key] = match
            return match

        # Try visual similarity (for re-rendered assets)
        visual_match, similarity = self._find_by_visual_similarity(
            source_asset, output_assets
        )
        if visual_match:
            # Use strict threshold for critical assets
            threshold = (
                VISUAL_SIMILARITY_STRICT
                if self.strict_mode and self._is_critical(source_asset)
                else self.visual_threshold
            )

            if similarity >= threshold:
                match = AssetMatch(
                    source_asset=source_asset,
                    output_asset=visual_match,
                    match_method="visual",
                    confidence=similarity,
                    matched=True,
                )
                self._match_cache[cache_key] = match
                return match

        # No match found
        match = AssetMatch(
            source_asset=source_asset,
            output_asset=None,
            match_method="none",
            confidence=0.0,
            matched=False,
        )
        self._match_cache[cache_key] = match
        return match

    def batch_match(
        self, source_assets: List[Asset], output_assets: List[dict]
    ) -> List[AssetMatch]:
        """
        Match all source assets to output assets.

        Args:
            source_assets: List of source assets
            output_assets: List of output assets

        Returns:
            List of AssetMatch results
        """
        matches = []
        for source_asset in source_assets:
            match = self.find_match(source_asset, output_assets)
            matches.append(match)
        return matches

    def _find_by_hash(
        self, source_asset: Asset, output_assets: List[dict]
    ) -> Optional[dict]:
        """
        Find exact hash match.

        Args:
            source_asset: Source asset to match
            output_assets: Output assets to search

        Returns:
            Matching output asset or None
        """
        for output_asset in output_assets:
            # Calculate hash if not already present
            if "sha256" not in output_asset:
                output_asset["sha256"] = calculate_hash(output_asset["data"])

            if output_asset["sha256"] == source_asset.sha256:
                return output_asset

        return None

    def _find_by_visual_similarity(
        self, source_asset: Asset, output_assets: List[dict]
    ) -> Tuple[Optional[dict], float]:
        """
        Find match by visual similarity.

        Args:
            source_asset: Source asset to match
            output_assets: Output assets to search

        Returns:
            Tuple of (best_match, similarity_score)
        """
        # Load source image
        source_image = load_image(source_asset.file_path)
        if not source_image:
            return None, 0.0

        best_match = None
        best_similarity = 0.0

        for output_asset in output_assets:
            # Convert output asset to image
            output_image = bytes_to_image(output_asset["data"])
            if not output_image:
                continue

            # Calculate similarity
            similarity = self._calculate_visual_similarity(source_image, output_image)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = output_asset

        return best_match, best_similarity

    def _calculate_visual_similarity(
        self, img1: Image.Image, img2: Image.Image, use_high_res: bool = False
    ) -> float:
        """
        Calculate visual similarity between two images.

        Uses perceptual hash and pixel comparison:
        1. Resize to standard size
        2. Convert to RGB
        3. Calculate mean squared error
        4. Convert to similarity score (0.0-1.0)

        Args:
            img1: First image
            img2: Second image
            use_high_res: Use higher resolution for comparison

        Returns:
            Similarity score (0.0-1.0, 1.0 = identical)
        """
        # Choose comparison size
        size = HIGH_RES_COMPARISON if use_high_res else COMPARISON_RESIZE

        # Resize and convert to RGB
        try:
            img1_resized = img1.resize(size).convert("RGB")
            img2_resized = img2.resize(size).convert("RGB")
        except Exception:
            return 0.0

        # Convert to numpy arrays
        arr1 = np.array(img1_resized, dtype=np.float32)
        arr2 = np.array(img2_resized, dtype=np.float32)

        # Calculate mean squared error
        mse = np.mean((arr1 - arr2) ** 2)

        # Convert MSE to similarity (0.0-1.0)
        # Max MSE for RGB is 255^2 * 3 = 195075
        max_mse = 255.0 ** 2 * 3
        similarity = 1.0 - (mse / max_mse)

        return max(0.0, min(1.0, similarity))

    def _calculate_perceptual_hash(self, image: Image.Image, hash_size: int = 8) -> str:
        """
        Calculate perceptual hash (pHash) of image.

        Args:
            image: PIL Image
            hash_size: Hash size (8 = 64-bit hash)

        Returns:
            Hex string of perceptual hash
        """
        # Resize and convert to grayscale
        img_resized = image.resize((hash_size, hash_size)).convert("L")

        # Get pixel data
        pixels = np.array(img_resized, dtype=np.float32)

        # Calculate average
        avg = pixels.mean()

        # Create hash (1 if pixel > avg, 0 otherwise)
        hash_bits = (pixels > avg).flatten()

        # Convert to hex string
        hash_int = int("".join(["1" if bit else "0" for bit in hash_bits]), 2)
        return f"{hash_int:016x}"

    def _hamming_distance(self, hash1: str, hash2: str) -> int:
        """
        Calculate Hamming distance between two hashes.

        Args:
            hash1: First hash (hex string)
            hash2: Second hash (hex string)

        Returns:
            Hamming distance (number of differing bits)
        """
        # Convert hex to int
        int1 = int(hash1, 16)
        int2 = int(hash2, 16)

        # XOR and count set bits
        xor = int1 ^ int2
        return bin(xor).count("1")

    def _is_critical(self, asset: Asset) -> bool:
        """
        Check if asset is critical (requires strict matching).

        Args:
            asset: Asset to check

        Returns:
            True if critical
        """
        # Large images are critical
        if asset.image_width and asset.image_width > CRITICAL_SIZE_THRESHOLD:
            return True
        if asset.image_height and asset.image_height > CRITICAL_SIZE_THRESHOLD:
            return True

        # Tables are critical
        if asset.asset_type in [AssetType.TABLE_LIVE, AssetType.TABLE_SNAP]:
            return True

        # Vectors are critical
        if asset.asset_type == AssetType.VECTOR_PDF:
            return True

        return False

    def get_match_statistics(self, matches: List[AssetMatch]) -> dict:
        """
        Calculate statistics for batch of matches.

        Args:
            matches: List of AssetMatch results

        Returns:
            Dictionary of statistics
        """
        total = len(matches)
        matched = sum(1 for m in matches if m.matched)
        hash_matches = sum(1 for m in matches if m.match_method == "hash")
        visual_matches = sum(1 for m in matches if m.match_method == "visual")
        no_matches = sum(1 for m in matches if m.match_method == "none")

        avg_confidence = (
            sum(m.confidence for m in matches if m.matched) / matched if matched else 0.0
        )

        return {
            "total": total,
            "matched": matched,
            "unmatched": no_matches,
            "match_rate": matched / total * 100 if total else 0.0,
            "hash_matches": hash_matches,
            "visual_matches": visual_matches,
            "average_confidence": avg_confidence,
        }

    def clear_cache(self):
        """Clear the match cache."""
        self._match_cache.clear()
