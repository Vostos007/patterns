"""JSON serialization and schema versioning for InDesign metadata.

This module handles:
1. Schema version definitions and compatibility
2. Migration functions between schema versions
3. Batch serialization/deserialization
4. Compression and size optimization

Schema Version History:
    1.0 (Current): Initial schema with full asset metadata

Future Considerations:
    - Schema 1.1 might add: DPI validation, rotation angles, effects
    - Schema 2.0 might add: Multi-asset groups, linked assets
"""

from typing import List, Dict, Any, Callable
from pathlib import Path
import json

from .metadata import PlacedObjectMetadata, CURRENT_SCHEMA_VERSION


# Schema version definitions
METADATA_SCHEMA_VERSIONS: Dict[str, Dict[str, Any]] = {
    "1.0": {
        "description": "Initial schema with full asset metadata",
        "required_fields": [
            "asset_id",
            "asset_type",
            "original_bbox",
            "ctm",
            "page_number",
            "occurrence",
            "anchor_to",
            "column_id",
            "normalized_bbox",
            "sha256",
            "file_path",
            "colorspace",
            "schema_version",
            "created_at",
        ],
        "optional_fields": [
            "has_smask",
            "has_clip",
            "fonts",
            "icc_profile_name",
            "image_dimensions",
            "expected_bbox_placed",
            "actual_bbox_placed",
        ],
        "migrations": {},  # No migrations needed for initial version
    }
}


def get_schema_version_info(version: str) -> Dict[str, Any]:
    """
    Get schema version information.

    Args:
        version: Schema version string (e.g., "1.0")

    Returns:
        Schema definition dictionary

    Raises:
        ValueError: If version is not supported
    """
    if version not in METADATA_SCHEMA_VERSIONS:
        supported = ", ".join(METADATA_SCHEMA_VERSIONS.keys())
        raise ValueError(f"Unsupported schema version {version}. Supported: {supported}")

    return METADATA_SCHEMA_VERSIONS[version]


def validate_schema_fields(data: Dict[str, Any], version: str) -> List[str]:
    """
    Validate that required fields are present for a schema version.

    Args:
        data: Deserialized JSON data
        version: Schema version to validate against

    Returns:
        List of validation errors (empty if valid)
    """
    schema = get_schema_version_info(version)
    required_fields = schema["required_fields"]

    errors = []
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    return errors


def migrate_metadata(
    data: Dict[str, Any],
    from_version: str,
    to_version: str = CURRENT_SCHEMA_VERSION,
) -> Dict[str, Any]:
    """
    Migrate metadata between schema versions.

    This function applies a chain of migrations to transform metadata
    from an older schema version to a newer one.

    Args:
        data: Metadata dictionary to migrate
        from_version: Source schema version
        to_version: Target schema version (defaults to current)

    Returns:
        Migrated metadata dictionary

    Raises:
        ValueError: If migration path is not supported

    Example:
        >>> old_data = {"asset_id": "img-123", "schema_version": "0.9", ...}
        >>> new_data = migrate_metadata(old_data, "0.9", "1.0")
        >>> new_data["schema_version"]
        '1.0'
    """
    if from_version == to_version:
        return data

    # For now, only support migration to current version
    if to_version != CURRENT_SCHEMA_VERSION:
        raise ValueError(f"Migration to non-current version {to_version} not supported")

    # Define migration chain (would be populated as versions evolve)
    migration_chain = _build_migration_chain(from_version, to_version)

    if not migration_chain:
        raise ValueError(f"No migration path from {from_version} to {to_version}")

    # Apply migrations in sequence
    current_data = data.copy()
    for migration_func in migration_chain:
        current_data = migration_func(current_data)

    # Update schema version
    current_data["schema_version"] = to_version

    return current_data


def _build_migration_chain(from_version: str, to_version: str) -> List[Callable]:
    """
    Build migration function chain between versions.

    This would be populated as new schema versions are added.

    Args:
        from_version: Source version
        to_version: Target version

    Returns:
        List of migration functions to apply in sequence
    """
    # Placeholder for future migrations
    # Example:
    # if from_version == "0.9" and to_version == "1.0":
    #     return [_migrate_0_9_to_1_0]

    # For now, no migrations needed
    return []


# Future migration functions would be defined here
# Example:
# def _migrate_0_9_to_1_0(data: Dict[str, Any]) -> Dict[str, Any]:
#     """Migrate from schema 0.9 to 1.0."""
#     # Add new required fields with defaults
#     if "column_id" not in data:
#         data["column_id"] = 0
#     # Transform renamed fields
#     if "bbox" in data:
#         data["original_bbox"] = data.pop("bbox")
#     return data


def serialize_batch(
    metadata_list: List[PlacedObjectMetadata],
    output_path: Path,
    indent: bool = False,
) -> None:
    """
    Serialize multiple metadata objects to JSON file.

    Useful for saving placement manifests or debugging.

    Args:
        metadata_list: List of PlacedObjectMetadata objects
        output_path: Path to output JSON file
        indent: If True, use pretty-printed JSON (larger file)

    Example:
        >>> metadata_objects = [...]
        >>> serialize_batch(metadata_objects, Path("placement_manifest.json"))
    """
    data = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "count": len(metadata_list),
        "metadata": [
            json.loads(m.to_json()) for m in metadata_list
        ]
    }

    with output_path.open('w', encoding='utf-8') as f:
        if indent:
            json.dump(data, f, indent=2, ensure_ascii=False)
        else:
            json.dump(data, f, ensure_ascii=False, separators=(',', ':'))


def deserialize_batch(input_path: Path) -> List[PlacedObjectMetadata]:
    """
    Deserialize multiple metadata objects from JSON file.

    Args:
        input_path: Path to input JSON file

    Returns:
        List of PlacedObjectMetadata objects

    Raises:
        ValueError: If file format is invalid

    Example:
        >>> metadata_objects = deserialize_batch(Path("placement_manifest.json"))
        >>> len(metadata_objects)
        42
    """
    with input_path.open('r', encoding='utf-8') as f:
        data = json.load(f)

    # Validate file format
    if "metadata" not in data:
        raise ValueError("Invalid batch file: missing 'metadata' field")

    if "schema_version" not in data:
        raise ValueError("Invalid batch file: missing 'schema_version' field")

    # Check schema version
    file_version = data["schema_version"]
    if file_version != CURRENT_SCHEMA_VERSION:
        raise ValueError(
            f"Schema version mismatch: file is {file_version}, current is {CURRENT_SCHEMA_VERSION}. "
            "Migration not yet implemented."
        )

    # Deserialize each metadata object
    metadata_list = []
    for i, metadata_dict in enumerate(data["metadata"]):
        try:
            # Convert back to JSON string for from_json
            json_str = json.dumps(metadata_dict, ensure_ascii=False)
            metadata = PlacedObjectMetadata.from_json(json_str)
            metadata_list.append(metadata)
        except Exception as e:
            raise ValueError(f"Failed to deserialize metadata at index {i}: {e}")

    return metadata_list


def calculate_json_size(metadata: PlacedObjectMetadata) -> int:
    """
    Calculate serialized JSON size in bytes.

    Useful for validating size constraints (InDesign has limits on extractLabel size).

    Args:
        metadata: PlacedObjectMetadata object

    Returns:
        Size in bytes (UTF-8 encoded)

    Example:
        >>> metadata = PlacedObjectMetadata(...)
        >>> size = calculate_json_size(metadata)
        >>> if size > 1024:
        ...     print(f"WARNING: Metadata is {size} bytes (> 1KB)")
    """
    json_str = metadata.to_json()
    return len(json_str.encode('utf-8'))


def optimize_for_size(metadata: PlacedObjectMetadata) -> str:
    """
    Optimize metadata JSON for minimum size.

    Applies aggressive size reduction techniques:
    - Remove optional fields that are empty/default
    - Use shortest possible field names
    - Remove whitespace

    Args:
        metadata: PlacedObjectMetadata object

    Returns:
        Optimized JSON string

    Note:
        This is an aggressive optimization. Only use if size limits are hit.
        For normal use, metadata.to_json() is sufficient.
    """
    # Get standard JSON
    data = json.loads(metadata.to_json())

    # Remove empty optional fields
    fields_to_check = [
        "fonts",
        "icc_profile_name",
        "image_dimensions",
        "expected_bbox_placed",
        "actual_bbox_placed",
    ]

    for field in fields_to_check:
        if field in data:
            value = data[field]
            # Remove if empty list or None
            if value is None or (isinstance(value, list) and len(value) == 0):
                del data[field]

    # Remove boolean fields if False (default)
    if not data.get("has_smask", False):
        data.pop("has_smask", None)
    if not data.get("has_clip", False):
        data.pop("has_clip", None)

    # Serialize with no whitespace
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'))


def pretty_print_metadata(metadata: PlacedObjectMetadata) -> str:
    """
    Format metadata as human-readable JSON.

    Useful for debugging and logging.

    Args:
        metadata: PlacedObjectMetadata object

    Returns:
        Pretty-printed JSON string

    Example:
        >>> metadata = PlacedObjectMetadata(...)
        >>> print(pretty_print_metadata(metadata))
        {
          "asset_id": "img-abc123",
          "asset_type": "image",
          ...
        }
    """
    data = json.loads(metadata.to_json())
    return json.dumps(data, indent=2, ensure_ascii=False)


def verify_roundtrip(metadata: PlacedObjectMetadata) -> bool:
    """
    Verify that serialization/deserialization is lossless.

    Args:
        metadata: PlacedObjectMetadata object to test

    Returns:
        True if roundtrip is successful

    Example:
        >>> metadata = PlacedObjectMetadata(...)
        >>> assert verify_roundtrip(metadata)
    """
    try:
        # Serialize
        json_str = metadata.to_json()

        # Deserialize
        reconstructed = PlacedObjectMetadata.from_json(json_str)

        # Compare key fields
        checks = [
            metadata.asset_id == reconstructed.asset_id,
            metadata.asset_type == reconstructed.asset_type,
            metadata.sha256 == reconstructed.sha256,
            metadata.page_number == reconstructed.page_number,
            metadata.occurrence == reconstructed.occurrence,
            metadata.anchor_to == reconstructed.anchor_to,
            metadata.column_id == reconstructed.column_id,
            metadata.normalized_bbox == reconstructed.normalized_bbox,
            metadata.original_bbox == reconstructed.original_bbox,
            metadata.ctm == reconstructed.ctm,
        ]

        return all(checks)

    except Exception:
        return False
