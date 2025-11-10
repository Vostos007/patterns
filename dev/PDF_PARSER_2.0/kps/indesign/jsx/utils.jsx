/**
 * JSX Utility Library for KPS InDesign Automation
 *
 * Provides common functions for JSON parsing, file I/O, bbox calculations,
 * and coordinate transformations used across KPS JSX scripts.
 *
 * Author: KPS v2.0 InDesign Automation
 * Last Modified: 2025-11-06
 */

// ============================================================================
// JSON Utilities
// ============================================================================

/**
 * Parse JSON from string with error handling.
 *
 * @param {string} jsonString - JSON string to parse
 * @returns {Object|null} Parsed object or null on error
 */
function parseJSON(jsonString) {
    try {
        // ExtendScript doesn't have native JSON.parse in older versions
        // Use eval with safety wrapper
        var parsed = eval('(' + jsonString + ')');
        return parsed;
    } catch (e) {
        $.writeln("ERROR: Failed to parse JSON: " + e.message);
        return null;
    }
}

/**
 * Convert object to JSON string.
 *
 * @param {Object} obj - Object to stringify
 * @param {number} indent - Indentation level (default: 0)
 * @returns {string} JSON string
 */
function stringifyJSON(obj, indent) {
    indent = indent || 0;
    var indentStr = new Array(indent + 1).join('  ');
    var nextIndent = indent + 1;
    var nextIndentStr = new Array(nextIndent + 1).join('  ');

    if (obj === null) {
        return 'null';
    }

    if (obj === undefined) {
        return 'undefined';
    }

    if (typeof obj === 'string') {
        return '"' + obj.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n') + '"';
    }

    if (typeof obj === 'number' || typeof obj === 'boolean') {
        return String(obj);
    }

    if (obj instanceof Array) {
        if (obj.length === 0) {
            return '[]';
        }
        var items = [];
        for (var i = 0; i < obj.length; i++) {
            items.push(nextIndentStr + stringifyJSON(obj[i], nextIndent));
        }
        return '[\n' + items.join(',\n') + '\n' + indentStr + ']';
    }

    if (typeof obj === 'object') {
        var keys = [];
        for (var key in obj) {
            if (obj.hasOwnProperty(key)) {
                keys.push(key);
            }
        }

        if (keys.length === 0) {
            return '{}';
        }

        var pairs = [];
        for (var j = 0; j < keys.length; j++) {
            var k = keys[j];
            pairs.push(nextIndentStr + '"' + k + '": ' + stringifyJSON(obj[k], nextIndent));
        }
        return '{\n' + pairs.join(',\n') + '\n' + indentStr + '}';
    }

    return 'null';
}

// ============================================================================
// File I/O Utilities
// ============================================================================

/**
 * Read text file contents.
 *
 * @param {string} filePath - Absolute path to file
 * @returns {string|null} File contents or null on error
 */
function readFile(filePath) {
    try {
        var file = new File(filePath);
        if (!file.exists) {
            $.writeln("ERROR: File not found: " + filePath);
            return null;
        }

        file.encoding = 'UTF-8';
        file.open('r');
        var content = file.read();
        file.close();

        return content;
    } catch (e) {
        $.writeln("ERROR: Failed to read file: " + e.message);
        return null;
    }
}

/**
 * Write text to file.
 *
 * @param {string} filePath - Absolute path to file
 * @param {string} content - Content to write
 * @returns {boolean} True on success, false on error
 */
function writeFile(filePath, content) {
    try {
        var file = new File(filePath);
        file.encoding = 'UTF-8';
        file.open('w');
        file.write(content);
        file.close();

        return true;
    } catch (e) {
        $.writeln("ERROR: Failed to write file: " + e.message);
        return false;
    }
}

/**
 * Load and parse JSON manifest file.
 *
 * @param {string} manifestPath - Path to manifest.json
 * @returns {Object|null} Parsed manifest or null on error
 */
function loadManifest(manifestPath) {
    var content = readFile(manifestPath);
    if (!content) {
        return null;
    }

    var manifest = parseJSON(content);
    if (!manifest) {
        $.writeln("ERROR: Invalid JSON in manifest file");
        return null;
    }

    // Validate manifest structure
    if (!manifest.assets || !manifest.assets.length) {
        $.writeln("ERROR: Manifest has no assets array");
        return null;
    }

    $.writeln("INFO: Loaded manifest with " + manifest.assets.length + " assets");
    return manifest;
}

// ============================================================================
// BBox Utilities
// ============================================================================

/**
 * Create BBox object from coordinates.
 *
 * @param {number} x0 - Left coordinate
 * @param {number} y0 - Bottom coordinate
 * @param {number} x1 - Right coordinate
 * @param {number} y1 - Top coordinate
 * @returns {Object} BBox object
 */
function createBBox(x0, y0, x1, y1) {
    return {
        x0: x0,
        y0: y0,
        x1: x1,
        y1: y1,
        width: x1 - x0,
        height: y1 - y0,
        center_x: (x0 + x1) / 2,
        center_y: (y0 + y1) / 2,
        area: (x1 - x0) * (y1 - y0)
    };
}

/**
 * Convert InDesign geometric bounds to BBox.
 * InDesign uses [y0, x0, y1, x1] format.
 *
 * @param {Array} bounds - InDesign geometricBounds [y0, x0, y1, x1]
 * @returns {Object} BBox object
 */
function geometricBoundsToBBox(bounds) {
    // InDesign format: [top, left, bottom, right]
    // Convert to PDF format: [left, bottom, right, top]
    return createBBox(
        bounds[1],  // x0 = left
        bounds[2],  // y0 = bottom
        bounds[3],  // x1 = right
        bounds[0]   // y1 = top
    );
}

/**
 * Convert BBox to InDesign geometric bounds.
 *
 * @param {Object} bbox - BBox object with x0, y0, x1, y1
 * @returns {Array} InDesign geometricBounds [y0, x0, y1, x1]
 */
function bboxToGeometricBounds(bbox) {
    // Convert PDF format to InDesign format
    return [
        bbox.y1,  // top
        bbox.x0,  // left
        bbox.y0,  // bottom
        bbox.x1   // right
    ];
}

/**
 * Calculate overlap ratio between two bboxes.
 *
 * @param {Object} bbox1 - First BBox
 * @param {Object} bbox2 - Second BBox
 * @returns {number} Overlap ratio (0-1)
 */
function calculateOverlap(bbox1, bbox2) {
    var overlapLeft = Math.max(bbox1.x0, bbox2.x0);
    var overlapRight = Math.min(bbox1.x1, bbox2.x1);
    var overlapBottom = Math.max(bbox1.y0, bbox2.y0);
    var overlapTop = Math.min(bbox1.y1, bbox2.y1);

    if (overlapLeft >= overlapRight || overlapBottom >= overlapTop) {
        return 0.0;
    }

    var overlapArea = (overlapRight - overlapLeft) * (overlapTop - overlapBottom);
    var minArea = Math.min(bbox1.area, bbox2.area);

    return overlapArea / minArea;
}

/**
 * Calculate distance between bbox centers.
 *
 * @param {Object} bbox1 - First BBox
 * @param {Object} bbox2 - Second BBox
 * @returns {number} Euclidean distance
 */
function calculateDistance(bbox1, bbox2) {
    var dx = bbox1.center_x - bbox2.center_x;
    var dy = bbox1.center_y - bbox2.center_y;
    return Math.sqrt(dx * dx + dy * dy);
}

// ============================================================================
// Coordinate Conversion Utilities
// ============================================================================

/**
 * Convert normalized coordinates (0-1) to absolute coordinates.
 *
 * @param {Object} normalized - {x, y, w, h} in 0-1 range
 * @param {Object} column - Column bounds {x_min, x_max, y_min, y_max}
 * @returns {Object} BBox with absolute coordinates
 */
function normalizedToAbsolute(normalized, column) {
    var x0 = column.x_min + normalized.x * (column.x_max - column.x_min);
    var y0 = column.y_min + normalized.y * (column.y_max - column.y_min);
    var width = normalized.w * (column.x_max - column.x_min);
    var height = normalized.h * (column.y_max - column.y_min);

    return createBBox(x0, y0, x0 + width, y0 + height);
}

/**
 * Convert absolute coordinates to normalized (0-1).
 *
 * @param {Object} bbox - BBox with absolute coordinates
 * @param {Object} column - Column bounds {x_min, x_max, y_min, y_max}
 * @returns {Object} Normalized coordinates {x, y, w, h}
 */
function absoluteToNormalized(bbox, column) {
    var columnWidth = column.x_max - column.x_min;
    var columnHeight = column.y_max - column.y_min;

    return {
        x: (bbox.x0 - column.x_min) / columnWidth,
        y: (bbox.y0 - column.y_min) / columnHeight,
        w: bbox.width / columnWidth,
        h: bbox.height / columnHeight
    };
}

// ============================================================================
// InDesign Document Utilities
// ============================================================================

/**
 * Get all page items (images, graphics, text frames) from document.
 *
 * @param {Document} doc - InDesign document
 * @returns {Array} Array of page items
 */
function getAllPageItems(doc) {
    var items = [];

    for (var i = 0; i < doc.pages.length; i++) {
        var page = doc.pages[i];

        // Get all images
        for (var j = 0; j < page.allGraphics.length; j++) {
            items.push(page.allGraphics[j]);
        }

        // Get rectangles (may contain graphics)
        for (var k = 0; k < page.rectangles.length; k++) {
            items.push(page.rectangles[k]);
        }
    }

    return items;
}

/**
 * Find page item by label.
 *
 * @param {Document} doc - InDesign document
 * @param {string} label - Label to search for
 * @returns {PageItem|null} Found item or null
 */
function findItemByLabel(doc, label) {
    var items = getAllPageItems(doc);

    for (var i = 0; i < items.length; i++) {
        if (items[i].label === label) {
            return items[i];
        }
    }

    return null;
}

/**
 * Get page number (0-indexed) for a page item.
 *
 * @param {PageItem} item - InDesign page item
 * @returns {number} Page number (0-indexed)
 */
function getPageNumber(item) {
    if (item.parentPage) {
        return item.parentPage.documentOffset;
    }
    return -1;
}

// ============================================================================
// Logging Utilities
// ============================================================================

/**
 * Log info message.
 *
 * @param {string} message - Message to log
 */
function logInfo(message) {
    $.writeln("INFO: " + message);
}

/**
 * Log warning message.
 *
 * @param {string} message - Message to log
 */
function logWarning(message) {
    $.writeln("WARNING: " + message);
}

/**
 * Log error message.
 *
 * @param {string} message - Message to log
 */
function logError(message) {
    $.writeln("ERROR: " + message);
}

/**
 * Log success message.
 *
 * @param {string} message - Message to log
 */
function logSuccess(message) {
    $.writeln("SUCCESS: " + message);
}

// ============================================================================
// Asset Matching Utilities
// ============================================================================

/**
 * Match page item to asset by position and size.
 *
 * @param {PageItem} item - InDesign page item
 * @param {Object} asset - Asset from manifest
 * @param {number} tolerance - Position tolerance in points
 * @returns {boolean} True if item matches asset
 */
function matchItemToAsset(item, asset, tolerance) {
    tolerance = tolerance || 5.0;

    // Get item bbox
    var itemBBox = geometricBoundsToBBox(item.geometricBounds);

    // Get asset bbox
    var assetBBox = createBBox(
        asset.bbox.x0,
        asset.bbox.y0,
        asset.bbox.x1,
        asset.bbox.y1
    );

    // Check page number
    var itemPage = getPageNumber(item);
    if (itemPage !== asset.page_number) {
        return false;
    }

    // Check position and size with tolerance
    var posMatch = (
        Math.abs(itemBBox.x0 - assetBBox.x0) <= tolerance &&
        Math.abs(itemBBox.y0 - assetBBox.y0) <= tolerance &&
        Math.abs(itemBBox.x1 - assetBBox.x1) <= tolerance &&
        Math.abs(itemBBox.y1 - assetBBox.y1) <= tolerance
    );

    return posMatch;
}

// ============================================================================
// Export utilities object for use in other scripts
// ============================================================================

// Make all functions available globally
var KPSUtils = {
    // JSON
    parseJSON: parseJSON,
    stringifyJSON: stringifyJSON,

    // File I/O
    readFile: readFile,
    writeFile: writeFile,
    loadManifest: loadManifest,

    // BBox
    createBBox: createBBox,
    geometricBoundsToBBox: geometricBoundsToBBox,
    bboxToGeometricBounds: bboxToGeometricBounds,
    calculateOverlap: calculateOverlap,
    calculateDistance: calculateDistance,

    // Coordinate conversion
    normalizedToAbsolute: normalizedToAbsolute,
    absoluteToNormalized: absoluteToNormalized,

    // InDesign
    getAllPageItems: getAllPageItems,
    findItemByLabel: findItemByLabel,
    getPageNumber: getPageNumber,

    // Logging
    logInfo: logInfo,
    logWarning: logWarning,
    logError: logError,
    logSuccess: logSuccess,

    // Asset matching
    matchItemToAsset: matchItemToAsset
};
