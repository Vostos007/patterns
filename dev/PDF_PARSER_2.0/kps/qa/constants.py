"""QA constants and thresholds for asset completeness checking."""

# Coverage thresholds
PERFECT_COVERAGE = 100.0
ACCEPTABLE_COVERAGE = 98.0
WARNING_COVERAGE = 95.0

# Asset matching thresholds
HASH_MATCH_PRIORITY = 1  # Exact hash match (highest priority)
VISUAL_MATCH_PRIORITY = 2  # Visual similarity match

VISUAL_SIMILARITY_THRESHOLD = 0.95  # 95% similarity required
VISUAL_SIMILARITY_STRICT = 0.98  # 98% for critical assets

# Critical asset thresholds
CRITICAL_SIZE_THRESHOLD = 500  # pixels - assets larger than this are critical
LARGE_ASSET_THRESHOLD = 1000  # pixels - very large assets
PROMINENT_AREA_THRESHOLD = 250000  # square pixels (e.g., 500x500)

# Image comparison settings
COMPARISON_RESIZE = (64, 64)  # Size for quick visual comparison
HIGH_RES_COMPARISON = (256, 256)  # For detailed comparison

# Visual diff thresholds
VISUAL_DIFF_PIXEL_THRESHOLD = 10  # Intensity delta considered a change (0-255)
VISUAL_DIFF_MAX_RATIO = 0.02  # Maximum allowed ratio of differing pixels (2%)
VISUAL_DIFF_MIN_COVERAGE = 0.001  # Minimum mask coverage to trust comparison

# Visual diff warnings
WARNING_LOW_MASK_COVERAGE = "Mask coverage below minimum threshold for reliable diff"

# Visual diff recommendations
RECOMMEND_VISUAL_REVIEW = "Inspect visual diff output for highlighted differences"

# Color audit warnings
WARNING_MISSING_ICC_PROFILE = "Missing ICC profile for CMYK/Lab asset"
WARNING_COLORSPACE_CONVERSION = "Colorspace conversion detected"

# Color audit recommendations
RECOMMEND_EMBED_ICC_PROFILES = "Embed CMYK/Lab ICC profiles in the exported PDF"
RECOMMEND_PRESERVE_COLOR_NUMBERS = "Ensure export preset preserves CMYK numbers to avoid unintended RGB conversion"

# Report settings
MAX_MISSING_DETAILS = 10  # Show first N missing assets in detail
MAX_ORPHAN_DETAILS = 5  # Show first N orphan assets in detail
MAX_RECOMMENDATIONS = 15  # Maximum recommendations to show

# Asset type weights (for prioritization)
ASSET_TYPE_WEIGHTS = {
    "image": 1.0,
    "vector_pdf": 1.2,  # Vectors are critical
    "vector_png": 1.0,
    "table_live": 1.5,  # Tables are very critical
    "table_snap": 1.5,
}

# Coverage color coding thresholds
COVERAGE_EXCELLENT = 100.0  # Green
COVERAGE_GOOD = 98.0  # Yellow
COVERAGE_ACCEPTABLE = 95.0  # Orange
COVERAGE_POOR = 90.0  # Red

# QA status
class QAStatus:
    """QA check status codes"""

    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    FAILED = "failed"
    ERROR = "error"


# Error messages
ERROR_NO_SOURCE_ASSETS = "No assets found in source ledger"
ERROR_NO_OUTPUT_PDF = "Output PDF not found"
ERROR_CORRUPT_OUTPUT = "Output PDF appears to be corrupt"
ERROR_EXTRACTION_FAILED = "Failed to extract assets from output PDF"

# Warning messages
WARNING_LOW_COVERAGE = "Coverage below acceptable threshold"
WARNING_MISSING_CRITICAL = "Critical assets missing from output"
WARNING_ORPHAN_ASSETS = "Orphan assets found in output (not in source)"
WARNING_PAGE_MISMATCH = "Page count mismatch between source and output"

# Recommendation templates
RECOMMEND_CHECK_ANCHORING = "Review anchoring configuration for missing assets"
RECOMMEND_CHECK_INDESIGN = "Verify InDesign placement script completed successfully"
RECOMMEND_MANUAL_REVIEW = "Manual review recommended for missing critical assets"
RECOMMEND_CHECK_FORMAT = "Check if asset format conversion is working correctly"
RECOMMEND_RERUN_PIPELINE = "Consider re-running the pipeline with updated settings"
