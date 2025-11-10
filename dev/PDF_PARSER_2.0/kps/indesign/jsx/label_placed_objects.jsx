/**
 * Label Placed Objects in InDesign
 *
 * This script labels existing placed objects (images, graphics) in an InDesign
 * document with their corresponding asset_ids from the manifest.json.
 *
 * Process:
 * 1. Load manifest.json with AssetLedger
 * 2. Iterate through all placed objects in document
 * 3. Match each object to asset by position/size/page
 * 4. Set object.label = asset_id
 * 5. Set object.extractLabel = JSON metadata
 *
 * Usage:
 *   Run from InDesign: File > Scripts > Run Script > label_placed_objects.jsx
 *   Or via Python: jsx_runner.label_placed_objects(document_path, manifest_path)
 *
 * Author: KPS v2.0 InDesign Automation
 * Last Modified: 2025-11-06
 */

// ============================================================================
// Load utilities
// ============================================================================

#include "utils.jsx"

// ============================================================================
// Configuration
// ============================================================================

var CONFIG = {
    POSITION_TOLERANCE: 5.0,  // Points tolerance for position matching
    SIZE_TOLERANCE: 2.0,      // Points tolerance for size matching
    MIN_CONFIDENCE: 0.8       // Minimum matching confidence
};

// ============================================================================
// Main Labeling Function
// ============================================================================

/**
 * Label all placed objects in active document.
 *
 * @param {string} manifestPath - Path to manifest.json
 * @returns {Object} Results summary
 */
function labelPlacedObjects(manifestPath) {
    // Validate active document
    if (!app.documents.length) {
        KPSUtils.logError("No active document. Please open an InDesign document.");
        return {
            success: false,
            error: "No active document"
        };
    }

    var doc = app.activeDocument;
    KPSUtils.logInfo("Processing document: " + doc.name);

    // Load manifest
    var manifest = KPSUtils.loadManifest(manifestPath);
    if (!manifest) {
        return {
            success: false,
            error: "Failed to load manifest"
        };
    }

    // Get all page items
    var items = KPSUtils.getAllPageItems(doc);
    KPSUtils.logInfo("Found " + items.length + " page items in document");

    // Track results
    var results = {
        success: true,
        total_items: items.length,
        labeled: 0,
        skipped: 0,
        errors: 0,
        labeled_items: [],
        skipped_items: [],
        error_items: []
    };

    // Process each item
    for (var i = 0; i < items.length; i++) {
        var item = items[i];

        try {
            var result = labelSingleItem(item, manifest, doc);

            if (result.success) {
                results.labeled++;
                results.labeled_items.push({
                    asset_id: result.asset_id,
                    page: result.page,
                    bbox: result.bbox
                });
                KPSUtils.logSuccess("Labeled: " + result.asset_id);
            } else if (result.skipped) {
                results.skipped++;
                results.skipped_items.push({
                    reason: result.reason,
                    page: KPSUtils.getPageNumber(item)
                });
                KPSUtils.logWarning("Skipped: " + result.reason);
            }
        } catch (e) {
            results.errors++;
            results.error_items.push({
                error: e.message,
                page: KPSUtils.getPageNumber(item)
            });
            KPSUtils.logError("Error processing item: " + e.message);
        }
    }

    // Log summary
    KPSUtils.logInfo("=== Labeling Complete ===");
    KPSUtils.logInfo("Labeled: " + results.labeled);
    KPSUtils.logInfo("Skipped: " + results.skipped);
    KPSUtils.logInfo("Errors: " + results.errors);

    return results;
}

/**
 * Label a single page item.
 *
 * @param {PageItem} item - InDesign page item
 * @param {Object} manifest - Manifest data
 * @param {Document} doc - InDesign document
 * @returns {Object} Result object
 */
function labelSingleItem(item, manifest, doc) {
    // Skip items that already have labels
    if (item.label && item.label.length > 0) {
        return {
            success: false,
            skipped: true,
            reason: "Already labeled: " + item.label
        };
    }

    // Skip items without parent page
    if (!item.parentPage) {
        return {
            success: false,
            skipped: true,
            reason: "No parent page"
        };
    }

    // Get item properties
    var itemPage = KPSUtils.getPageNumber(item);
    var itemBBox = KPSUtils.geometricBoundsToBBox(item.geometricBounds);

    // Find matching asset
    var matchResult = findMatchingAsset(item, itemBBox, itemPage, manifest);

    if (!matchResult.found) {
        return {
            success: false,
            skipped: true,
            reason: "No matching asset found"
        };
    }

    var asset = matchResult.asset;

    // Set label
    item.label = asset.asset_id;

    // Prepare metadata for extractLabel
    var metadata = {
        asset_id: asset.asset_id,
        asset_type: asset.asset_type,
        sha256: asset.sha256,
        page_number: asset.page_number,
        original_bbox: {
            x0: asset.bbox.x0,
            y0: asset.bbox.y0,
            x1: asset.bbox.x1,
            y1: asset.bbox.y1
        },
        placed_bbox: {
            x0: itemBBox.x0,
            y0: itemBBox.y0,
            x1: itemBBox.x1,
            y1: itemBBox.y1
        },
        ctm: asset.ctm,
        anchor_to: asset.anchor_to,
        occurrence: asset.occurrence,
        match_confidence: matchResult.confidence
    };

    // Set extractLabel
    item.extractLabel = KPSUtils.stringifyJSON(metadata);

    return {
        success: true,
        asset_id: asset.asset_id,
        page: itemPage,
        bbox: itemBBox,
        confidence: matchResult.confidence
    };
}

/**
 * Find matching asset for a page item.
 *
 * Matching strategy:
 * 1. Filter by page number
 * 2. Calculate position/size similarity
 * 3. Return best match above confidence threshold
 *
 * @param {PageItem} item - InDesign page item
 * @param {Object} itemBBox - Item bounding box
 * @param {number} itemPage - Item page number
 * @param {Object} manifest - Manifest data
 * @returns {Object} Match result {found, asset, confidence}
 */
function findMatchingAsset(item, itemBBox, itemPage, manifest) {
    var bestMatch = null;
    var bestConfidence = 0.0;

    // Filter assets by page
    var pageAssets = [];
    for (var i = 0; i < manifest.assets.length; i++) {
        if (manifest.assets[i].page_number === itemPage) {
            pageAssets.push(manifest.assets[i]);
        }
    }

    if (pageAssets.length === 0) {
        return {found: false, asset: null, confidence: 0.0};
    }

    // Calculate confidence for each asset
    for (var j = 0; j < pageAssets.length; j++) {
        var asset = pageAssets[j];
        var assetBBox = KPSUtils.createBBox(
            asset.bbox.x0,
            asset.bbox.y0,
            asset.bbox.x1,
            asset.bbox.y1
        );

        var confidence = calculateMatchConfidence(itemBBox, assetBBox);

        if (confidence > bestConfidence) {
            bestConfidence = confidence;
            bestMatch = asset;
        }
    }

    // Return best match if above threshold
    if (bestConfidence >= CONFIG.MIN_CONFIDENCE) {
        return {
            found: true,
            asset: bestMatch,
            confidence: bestConfidence
        };
    }

    return {found: false, asset: null, confidence: bestConfidence};
}

/**
 * Calculate match confidence between two bboxes.
 *
 * Confidence is based on:
 * - Position similarity (center point distance)
 * - Size similarity (width/height match)
 * - Overall overlap
 *
 * @param {Object} bbox1 - First bbox
 * @param {Object} bbox2 - Second bbox
 * @returns {number} Confidence score (0-1)
 */
function calculateMatchConfidence(bbox1, bbox2) {
    // Position similarity (0-1, 1 = perfect match)
    var distance = KPSUtils.calculateDistance(bbox1, bbox2);
    var maxDim = Math.max(bbox1.width, bbox1.height, bbox2.width, bbox2.height);
    var positionScore = Math.max(0, 1 - (distance / (maxDim * 2)));

    // Size similarity (0-1, 1 = perfect match)
    var widthRatio = Math.min(bbox1.width, bbox2.width) / Math.max(bbox1.width, bbox2.width);
    var heightRatio = Math.min(bbox1.height, bbox2.height) / Math.max(bbox1.height, bbox2.height);
    var sizeScore = (widthRatio + heightRatio) / 2;

    // Overlap similarity
    var overlapScore = KPSUtils.calculateOverlap(bbox1, bbox2);

    // Weighted average
    var confidence = (
        positionScore * 0.3 +
        sizeScore * 0.3 +
        overlapScore * 0.4
    );

    return confidence;
}

// ============================================================================
// CLI Interface
// ============================================================================

/**
 * Main entry point when run as standalone script.
 */
function main() {
    // Check for command-line arguments
    // In ExtendScript, arguments are passed via app.scriptArgs
    var manifestPath = null;

    // Try to get manifest path from script arguments
    if (typeof app.scriptArgs !== 'undefined' && app.scriptArgs.isDefined("manifestPath")) {
        manifestPath = app.scriptArgs.getValue("manifestPath");
    }

    // If no argument, prompt user
    if (!manifestPath) {
        var file = File.openDialog("Select manifest.json file", "JSON:*.json");
        if (file) {
            manifestPath = file.fsName;
        } else {
            alert("No manifest file selected. Exiting.");
            return;
        }
    }

    // Run labeling
    var results = labelPlacedObjects(manifestPath);

    // Show results dialog
    if (results.success) {
        var message = "Labeling Complete!\n\n";
        message += "Labeled: " + results.labeled + "\n";
        message += "Skipped: " + results.skipped + "\n";
        message += "Errors: " + results.errors + "\n";
        alert(message);
    } else {
        alert("Labeling failed: " + results.error);
    }
}

// Run if executed directly
if (typeof app !== 'undefined') {
    main();
}
