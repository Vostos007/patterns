/**
 * Place Assets from Manifest in InDesign
 *
 * This script automates the placement of visual assets in an InDesign document
 * based on manifest.json and KPSDocument JSON with [[asset_id]] markers.
 *
 * Process:
 * 1. Load manifest.json (AssetLedger)
 * 2. Load KPSDocument JSON (translated text with markers)
 * 3. For each asset in manifest:
 *    - Calculate placement position from normalized coordinates
 *    - Place asset file at calculated position
 *    - Set label and metadata
 *    - Apply transforms (rotation, scaling) if needed
 *
 * Usage:
 *   Run from InDesign: File > Scripts > Run Script > place_assets_from_manifest.jsx
 *   Or via Python: jsx_runner.place_assets(document_path, manifest_path, assets_dir)
 *
 * Input Requirements:
 *   - manifest.json with AssetLedger
 *   - Column layout information (for coordinate conversion)
 *   - Asset files in specified directory
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
    DPI: 72,                    // InDesign uses 72 DPI
    DEFAULT_FRAME_FITTING: FitOptions.PROPORTIONALLY,
    PRESERVE_ASPECT_RATIO: true,
    AUTO_LABEL: true,
    APPLY_CTM: true             // Apply transformation matrices
};

// ============================================================================
// Main Placement Function
// ============================================================================

/**
 * Place all assets from manifest into active document.
 *
 * @param {string} manifestPath - Path to manifest.json
 * @param {string} assetsDir - Directory containing asset files
 * @param {Object} columnLayout - Column layout info (optional)
 * @returns {Object} Placement results
 */
function placeAssetsFromManifest(manifestPath, assetsDir, columnLayout) {
    // Validate active document
    if (!app.documents.length) {
        KPSUtils.logError("No active document. Please open an InDesign document.");
        return {
            success: false,
            error: "No active document"
        };
    }

    var doc = app.activeDocument;
    KPSUtils.logInfo("Placing assets in document: " + doc.name);

    // Load manifest
    var manifest = KPSUtils.loadManifest(manifestPath);
    if (!manifest) {
        return {
            success: false,
            error: "Failed to load manifest"
        };
    }

    // Validate assets directory
    var assetsFolder = new Folder(assetsDir);
    if (!assetsFolder.exists) {
        KPSUtils.logError("Assets directory not found: " + assetsDir);
        return {
            success: false,
            error: "Assets directory not found"
        };
    }

    // Track results
    var results = {
        success: true,
        total_assets: manifest.assets.length,
        placed: 0,
        skipped: 0,
        errors: 0,
        placed_assets: [],
        skipped_assets: [],
        error_assets: []
    };

    // Process each asset
    for (var i = 0; i < manifest.assets.length; i++) {
        var asset = manifest.assets[i];

        try {
            var result = placeSingleAsset(asset, doc, assetsDir, columnLayout);

            if (result.success) {
                results.placed++;
                results.placed_assets.push({
                    asset_id: asset.asset_id,
                    page: asset.page_number,
                    file: result.file_path
                });
                KPSUtils.logSuccess("Placed: " + asset.asset_id);
            } else if (result.skipped) {
                results.skipped++;
                results.skipped_assets.push({
                    asset_id: asset.asset_id,
                    reason: result.reason
                });
                KPSUtils.logWarning("Skipped: " + asset.asset_id + " - " + result.reason);
            }
        } catch (e) {
            results.errors++;
            results.error_assets.push({
                asset_id: asset.asset_id,
                error: e.message
            });
            KPSUtils.logError("Error placing " + asset.asset_id + ": " + e.message);
        }
    }

    // Log summary
    KPSUtils.logInfo("=== Placement Complete ===");
    KPSUtils.logInfo("Placed: " + results.placed);
    KPSUtils.logInfo("Skipped: " + results.skipped);
    KPSUtils.logInfo("Errors: " + results.errors);

    return results;
}

/**
 * Place a single asset in the document.
 *
 * @param {Object} asset - Asset from manifest
 * @param {Document} doc - InDesign document
 * @param {string} assetsDir - Assets directory
 * @param {Object} columnLayout - Column layout (optional)
 * @returns {Object} Placement result
 */
function placeSingleAsset(asset, doc, assetsDir, columnLayout) {
    // Construct asset file path
    var assetFilePath = assetsDir + "/" + asset.file_path;
    var assetFile = new File(assetFilePath);

    if (!assetFile.exists) {
        // Try relative path from manifest
        assetFile = new File(asset.file_path);
        if (!assetFile.exists) {
            return {
                success: false,
                skipped: true,
                reason: "Asset file not found: " + asset.file_path
            };
        }
    }

    // Get target page
    if (asset.page_number >= doc.pages.length) {
        return {
            success: false,
            skipped: true,
            reason: "Page " + asset.page_number + " does not exist"
        };
    }

    var targetPage = doc.pages[asset.page_number];

    // Calculate placement bounds
    var placementBounds = calculatePlacementBounds(asset, targetPage, columnLayout);

    // Create rectangle frame for the asset
    var frame = targetPage.rectangles.add();

    // Set frame bounds (InDesign format: [y1, x0, y0, x1])
    var indesignBounds = KPSUtils.bboxToGeometricBounds(placementBounds);
    frame.geometricBounds = indesignBounds;

    // Place the asset file
    try {
        frame.place(assetFile);
    } catch (e) {
        // Clean up frame if placement fails
        frame.remove();
        return {
            success: false,
            error: true,
            reason: "Failed to place file: " + e.message
        };
    }

    // Apply frame fitting
    if (frame.images.length > 0) {
        frame.fit(CONFIG.DEFAULT_FRAME_FITTING);
    }

    // Apply transformation matrix if configured
    if (CONFIG.APPLY_CTM && asset.ctm) {
        try {
            applyCTM(frame, asset.ctm);
        } catch (e) {
            KPSUtils.logWarning("Failed to apply CTM: " + e.message);
        }
    }

    // Set label if configured
    if (CONFIG.AUTO_LABEL) {
        frame.label = asset.asset_id;

        // Set metadata
        var metadata = {
            asset_id: asset.asset_id,
            asset_type: asset.asset_type,
            sha256: asset.sha256,
            page_number: asset.page_number,
            original_bbox: asset.bbox,
            placed_bbox: {
                x0: placementBounds.x0,
                y0: placementBounds.y0,
                x1: placementBounds.x1,
                y1: placementBounds.y1
            },
            ctm: asset.ctm,
            anchor_to: asset.anchor_to,
            occurrence: asset.occurrence,
            placed_at: getTimestamp()
        };

        frame.extractLabel = KPSUtils.stringifyJSON(metadata);
    }

    return {
        success: true,
        frame: frame,
        file_path: asset.file_path
    };
}

/**
 * Calculate placement bounds for an asset.
 *
 * This function converts PDF coordinates to InDesign coordinates,
 * taking into account column layout if provided.
 *
 * @param {Object} asset - Asset from manifest
 * @param {Page} page - InDesign page
 * @param {Object} columnLayout - Column layout (optional)
 * @returns {Object} BBox for placement
 */
function calculatePlacementBounds(asset, page, columnLayout) {
    var assetBBox = KPSUtils.createBBox(
        asset.bbox.x0,
        asset.bbox.y0,
        asset.bbox.x1,
        asset.bbox.y1
    );

    // If column layout provided, use normalized coordinates
    if (columnLayout && columnLayout.columns) {
        // Find asset's column
        var column = findAssetColumn(asset, columnLayout.columns);

        if (column && asset.normalized_bbox) {
            // Convert normalized coords to absolute
            var normalized = {
                x: asset.normalized_bbox.x,
                y: asset.normalized_bbox.y,
                w: asset.normalized_bbox.w,
                h: asset.normalized_bbox.h
            };

            return KPSUtils.normalizedToAbsolute(normalized, column);
        }
    }

    // Default: use original bbox from PDF
    // Convert PDF coordinates to InDesign coordinates if needed
    var pageBounds = page.bounds;  // [y1, x0, y0, x1]
    var pageHeight = pageBounds[2] - pageBounds[0];

    // PDF has origin at bottom-left, InDesign at top-left
    // Need to flip y-coordinates
    var indesignBBox = KPSUtils.createBBox(
        assetBBox.x0,
        pageHeight - assetBBox.y1,  // Flip y
        assetBBox.x1,
        pageHeight - assetBBox.y0   // Flip y
    );

    return indesignBBox;
}

/**
 * Find which column an asset belongs to.
 *
 * @param {Object} asset - Asset from manifest
 * @param {Array} columns - Column definitions
 * @returns {Object|null} Column object or null
 */
function findAssetColumn(asset, columns) {
    var assetBBox = KPSUtils.createBBox(
        asset.bbox.x0,
        asset.bbox.y0,
        asset.bbox.x1,
        asset.bbox.y1
    );

    var bestColumn = null;
    var maxOverlap = 0.0;

    for (var i = 0; i < columns.length; i++) {
        var column = columns[i];
        var columnBBox = KPSUtils.createBBox(
            column.x_min,
            column.y_min,
            column.x_max,
            column.y_max
        );

        var overlap = KPSUtils.calculateOverlap(assetBBox, columnBBox);
        if (overlap > maxOverlap) {
            maxOverlap = overlap;
            bestColumn = column;
        }
    }

    return bestColumn;
}

/**
 * Apply transformation matrix to a frame.
 *
 * CTM format: [a, b, c, d, e, f]
 * - a: horizontal scaling
 * - b: vertical skewing
 * - c: horizontal skewing
 * - d: vertical scaling
 * - e: horizontal translation
 * - f: vertical translation
 *
 * @param {Rectangle} frame - InDesign frame
 * @param {Array} ctm - Transformation matrix
 */
function applyCTM(frame, ctm) {
    if (!ctm || ctm.length !== 6) {
        return;
    }

    var a = ctm[0];  // Scale X
    var b = ctm[1];  // Skew Y
    var c = ctm[2];  // Skew X
    var d = ctm[3];  // Scale Y
    var e = ctm[4];  // Translate X
    var f = ctm[5];  // Translate Y

    // Apply scaling
    if (a !== 1.0) {
        frame.horizontalScale = a * 100;  // Convert to percentage
    }
    if (d !== 1.0) {
        frame.verticalScale = d * 100;
    }

    // Apply rotation if needed
    // Calculate rotation from skew components
    if (b !== 0 || c !== 0) {
        var rotation = Math.atan2(b, a) * (180 / Math.PI);
        frame.rotationAngle = rotation;
    }

    // Apply shear if needed
    if (c !== 0 && b === 0) {
        frame.shearAngle = Math.atan(c / a) * (180 / Math.PI);
    }

    // Note: Translation (e, f) is already handled in placement bounds
}

/**
 * Get current timestamp in ISO format.
 *
 * @returns {string} ISO timestamp
 */
function getTimestamp() {
    var now = new Date();
    var year = now.getFullYear();
    var month = padZero(now.getMonth() + 1);
    var day = padZero(now.getDate());
    var hours = padZero(now.getHours());
    var minutes = padZero(now.getMinutes());
    var seconds = padZero(now.getSeconds());

    return year + "-" + month + "-" + day + "T" + hours + ":" + minutes + ":" + seconds;
}

/**
 * Pad number with leading zero.
 *
 * @param {number} num - Number to pad
 * @returns {string} Padded string
 */
function padZero(num) {
    return num < 10 ? "0" + num : String(num);
}

// ============================================================================
// Batch Operations
// ============================================================================

/**
 * Place assets by page range.
 *
 * @param {string} manifestPath - Path to manifest.json
 * @param {string} assetsDir - Assets directory
 * @param {number} startPage - Start page (0-indexed)
 * @param {number} endPage - End page (0-indexed, inclusive)
 * @param {Object} columnLayout - Column layout (optional)
 * @returns {Object} Placement results
 */
function placeAssetsByPageRange(manifestPath, assetsDir, startPage, endPage, columnLayout) {
    // Load manifest
    var manifest = KPSUtils.loadManifest(manifestPath);
    if (!manifest) {
        return {
            success: false,
            error: "Failed to load manifest"
        };
    }

    // Filter assets by page range
    var filteredAssets = [];
    for (var i = 0; i < manifest.assets.length; i++) {
        var asset = manifest.assets[i];
        if (asset.page_number >= startPage && asset.page_number <= endPage) {
            filteredAssets.push(asset);
        }
    }

    // Create filtered manifest
    var filteredManifest = {
        source_pdf: manifest.source_pdf,
        total_pages: manifest.total_pages,
        assets: filteredAssets
    };

    // Save filtered manifest temporarily
    var tempManifestPath = Folder.temp + "/kps_filtered_manifest.json";
    KPSUtils.writeFile(tempManifestPath, KPSUtils.stringifyJSON(filteredManifest));

    // Place assets
    return placeAssetsFromManifest(tempManifestPath, assetsDir, columnLayout);
}

// ============================================================================
// CLI Interface
// ============================================================================

/**
 * Main entry point when run as standalone script.
 */
function main() {
    // Check for command-line arguments
    var manifestPath = null;
    var assetsDir = null;

    // Try to get paths from script arguments
    if (typeof app.scriptArgs !== 'undefined') {
        if (app.scriptArgs.isDefined("manifestPath")) {
            manifestPath = app.scriptArgs.getValue("manifestPath");
        }
        if (app.scriptArgs.isDefined("assetsDir")) {
            assetsDir = app.scriptArgs.getValue("assetsDir");
        }
    }

    // Prompt for manifest if not provided
    if (!manifestPath) {
        var file = File.openDialog("Select manifest.json file", "JSON:*.json");
        if (file) {
            manifestPath = file.fsName;
        } else {
            alert("No manifest file selected. Exiting.");
            return;
        }
    }

    // Prompt for assets directory if not provided
    if (!assetsDir) {
        var folder = Folder.selectDialog("Select assets directory");
        if (folder) {
            assetsDir = folder.fsName;
        } else {
            alert("No assets directory selected. Exiting.");
            return;
        }
    }

    // Run placement
    var results = placeAssetsFromManifest(manifestPath, assetsDir, null);

    // Show results dialog
    if (results.success) {
        var message = "Asset Placement Complete!\n\n";
        message += "Placed: " + results.placed + "\n";
        message += "Skipped: " + results.skipped + "\n";
        message += "Errors: " + results.errors + "\n";

        if (results.errors > 0) {
            message += "\nSee console log for error details.";
        }

        alert(message);
    } else {
        alert("Placement failed: " + results.error);
    }
}

// Run if executed directly
if (typeof app !== 'undefined') {
    main();
}
