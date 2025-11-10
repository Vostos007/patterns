/**
 * Extract Object Labels from InDesign
 *
 * This script extracts labels and metadata from labeled objects in an InDesign
 * document and exports them to JSON format.
 *
 * Process:
 * 1. Iterate through all placed objects in document
 * 2. Extract object.label (asset_id)
 * 3. Extract object.extractLabel (JSON metadata)
 * 4. Export to JSON file with complete object information
 *
 * Usage:
 *   Run from InDesign: File > Scripts > Run Script > extract_object_labels.jsx
 *   Or via Python: jsx_runner.extract_labels(document_path, output_path)
 *
 * Output Format:
 *   {
 *     "document": "document_name.indd",
 *     "extracted_at": "2025-11-06T12:00:00",
 *     "objects": [
 *       {
 *         "label": "img-abc123-p0-occ1",
 *         "page": 0,
 *         "current_bbox": {...},
 *         "metadata": {...}  // from extractLabel
 *       }
 *     ]
 *   }
 *
 * Author: KPS v2.0 InDesign Automation
 * Last Modified: 2025-11-06
 */

// ============================================================================
// Load utilities
// ============================================================================

#include "utils.jsx"

// ============================================================================
// Main Extraction Function
// ============================================================================

/**
 * Extract labels from all objects in active document.
 *
 * @param {string} outputPath - Path to output JSON file (optional)
 * @returns {Object} Extraction results
 */
function extractObjectLabels(outputPath) {
    // Validate active document
    if (!app.documents.length) {
        KPSUtils.logError("No active document. Please open an InDesign document.");
        return {
            success: false,
            error: "No active document"
        };
    }

    var doc = app.activeDocument;
    KPSUtils.logInfo("Extracting labels from: " + doc.name);

    // Get all page items
    var items = KPSUtils.getAllPageItems(doc);
    KPSUtils.logInfo("Found " + items.length + " page items in document");

    // Extract data
    var extractedObjects = [];
    var labeledCount = 0;
    var unlabeledCount = 0;

    for (var i = 0; i < items.length; i++) {
        var item = items[i];

        // Skip items without labels
        if (!item.label || item.label.length === 0) {
            unlabeledCount++;
            continue;
        }

        try {
            var objData = extractSingleObject(item);
            if (objData) {
                extractedObjects.push(objData);
                labeledCount++;
            }
        } catch (e) {
            KPSUtils.logError("Error extracting object: " + e.message);
        }
    }

    // Prepare output data
    var outputData = {
        document: doc.name,
        document_path: doc.fullName.fsName,
        extracted_at: getTimestamp(),
        total_items: items.length,
        labeled_items: labeledCount,
        unlabeled_items: unlabeledCount,
        objects: extractedObjects
    };

    // Write to file if output path provided
    if (outputPath) {
        var success = KPSUtils.writeFile(outputPath, KPSUtils.stringifyJSON(outputData, 0));
        if (success) {
            KPSUtils.logSuccess("Exported to: " + outputPath);
        } else {
            KPSUtils.logError("Failed to write output file");
            return {
                success: false,
                error: "Failed to write output file"
            };
        }
    }

    // Log summary
    KPSUtils.logInfo("=== Extraction Complete ===");
    KPSUtils.logInfo("Labeled objects: " + labeledCount);
    KPSUtils.logInfo("Unlabeled objects: " + unlabeledCount);

    return {
        success: true,
        data: outputData
    };
}

/**
 * Extract data from a single page item.
 *
 * @param {PageItem} item - InDesign page item
 * @returns {Object|null} Extracted object data
 */
function extractSingleObject(item) {
    // Get basic properties
    var label = item.label;
    var page = KPSUtils.getPageNumber(item);
    var currentBBox = KPSUtils.geometricBoundsToBBox(item.geometricBounds);

    // Get item type
    var itemType = getItemType(item);

    // Parse metadata from extractLabel
    var metadata = null;
    if (item.extractLabel && item.extractLabel.length > 0) {
        try {
            metadata = KPSUtils.parseJSON(item.extractLabel);
        } catch (e) {
            KPSUtils.logWarning("Failed to parse extractLabel for: " + label);
        }
    }

    // Build object data
    var objData = {
        label: label,
        page: page,
        item_type: itemType,
        current_bbox: {
            x0: currentBBox.x0,
            y0: currentBBox.y0,
            x1: currentBBox.x1,
            y1: currentBBox.y1,
            width: currentBBox.width,
            height: currentBBox.height
        },
        geometric_bounds: item.geometricBounds,
        visible: item.visible,
        locked: item.locked
    };

    // Add metadata if available
    if (metadata) {
        objData.metadata = metadata;

        // Check if position has changed
        if (metadata.placed_bbox) {
            var originalBBox = KPSUtils.createBBox(
                metadata.placed_bbox.x0,
                metadata.placed_bbox.y0,
                metadata.placed_bbox.x1,
                metadata.placed_bbox.y1
            );
            var distance = KPSUtils.calculateDistance(currentBBox, originalBBox);
            objData.position_changed = distance > 1.0;  // Tolerance: 1 point
            objData.position_delta = distance;
        }
    }

    return objData;
}

/**
 * Get item type string.
 *
 * @param {PageItem} item - InDesign page item
 * @returns {string} Item type
 */
function getItemType(item) {
    var constructorName = item.constructor.name;

    // Map InDesign types to readable names
    var typeMap = {
        "Image": "image",
        "Graphic": "graphic",
        "Rectangle": "rectangle",
        "TextFrame": "text_frame",
        "Polygon": "polygon",
        "Oval": "oval",
        "Group": "group"
    };

    return typeMap[constructorName] || constructorName.toLowerCase();
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
// Analysis Functions
// ============================================================================

/**
 * Analyze extracted labels for consistency.
 *
 * Checks:
 * - Duplicate labels
 * - Missing metadata
 * - Position changes
 *
 * @param {Array} objects - Extracted objects
 * @returns {Object} Analysis results
 */
function analyzeLabels(objects) {
    var labelCounts = {};
    var missingMetadata = [];
    var positionChanged = [];

    for (var i = 0; i < objects.length; i++) {
        var obj = objects[i];

        // Count label occurrences
        if (!labelCounts[obj.label]) {
            labelCounts[obj.label] = 0;
        }
        labelCounts[obj.label]++;

        // Check for missing metadata
        if (!obj.metadata) {
            missingMetadata.push(obj.label);
        }

        // Check for position changes
        if (obj.position_changed) {
            positionChanged.push({
                label: obj.label,
                delta: obj.position_delta
            });
        }
    }

    // Find duplicates
    var duplicates = [];
    for (var label in labelCounts) {
        if (labelCounts[label] > 1) {
            duplicates.push({
                label: label,
                count: labelCounts[label]
            });
        }
    }

    return {
        total_objects: objects.length,
        unique_labels: Object.keys(labelCounts).length,
        duplicates: duplicates,
        missing_metadata: missingMetadata,
        position_changed: positionChanged
    };
}

// ============================================================================
// CLI Interface
// ============================================================================

/**
 * Main entry point when run as standalone script.
 */
function main() {
    // Check for command-line arguments
    var outputPath = null;

    // Try to get output path from script arguments
    if (typeof app.scriptArgs !== 'undefined' && app.scriptArgs.isDefined("outputPath")) {
        outputPath = app.scriptArgs.getValue("outputPath");
    }

    // If no argument, prompt user
    if (!outputPath) {
        var file = File.saveDialog("Save extracted labels as JSON", "JSON:*.json");
        if (file) {
            outputPath = file.fsName;
        } else {
            alert("No output file selected. Exiting.");
            return;
        }
    }

    // Run extraction
    var results = extractObjectLabels(outputPath);

    // Show results dialog
    if (results.success) {
        var data = results.data;
        var analysis = analyzeLabels(data.objects);

        var message = "Extraction Complete!\n\n";
        message += "Labeled objects: " + data.labeled_items + "\n";
        message += "Unlabeled objects: " + data.unlabeled_items + "\n";
        message += "Unique labels: " + analysis.unique_labels + "\n";

        if (analysis.duplicates.length > 0) {
            message += "\nWARNING: " + analysis.duplicates.length + " duplicate labels found!";
        }

        if (analysis.missing_metadata.length > 0) {
            message += "\nWARNING: " + analysis.missing_metadata.length + " objects missing metadata!";
        }

        if (analysis.position_changed.length > 0) {
            message += "\nINFO: " + analysis.position_changed.length + " objects moved from original position.";
        }

        alert(message);
    } else {
        alert("Extraction failed: " + results.error);
    }
}

// Run if executed directly
if (typeof app !== 'undefined') {
    main();
}
