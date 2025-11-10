/**
 * InDesign PDF/X-4 Export Script
 *
 * Exports InDesign documents to PDF with custom export settings.
 * Supports PDF/X-4:2010, PDF/X-1a, and other standards.
 *
 * Usage from ExtendScript:
 *   var result = exportToPDFX4(docPath, outputPath, settingsJSON);
 *
 * Author: KPS v2.0 Agent 4
 * Date: 2025-11-06
 */

#target indesign
#targetengine "session"

/**
 * Main export function - exports InDesign document to PDF/X-4
 *
 * @param {String} documentPath - Full path to InDesign document (.indd)
 * @param {String} outputPath - Full path for output PDF file
 * @param {Object} presetSettings - Export settings object (optional)
 * @returns {Object} Export result with success status and metadata
 */
function exportToPDFX4(documentPath, outputPath, presetSettings) {
    try {
        // Validate inputs
        if (!documentPath || !outputPath) {
            throw new Error("documentPath and outputPath are required");
        }

        // Open document
        var doc = openDocument(documentPath);

        // Apply export settings
        if (presetSettings) {
            applyExportSettings(doc, presetSettings);
        } else {
            // Use default high-quality settings
            applyDefaultSettings(doc);
        }

        // Export to PDF
        var pdfFile = new File(outputPath);
        var result = exportDocument(doc, pdfFile);

        // Close document (don't save changes)
        doc.close(SaveOptions.NO);

        return {
            success: true,
            output_path: outputPath,
            file_size: pdfFile.length,
            page_count: result.pageCount,
            export_time: result.exportTime,
            message: "PDF export completed successfully"
        };

    } catch (error) {
        return {
            success: false,
            error: error.message,
            error_line: error.line,
            message: "PDF export failed: " + error.message
        };
    }
}

/**
 * Open InDesign document with error handling
 *
 * @param {String} documentPath - Path to document
 * @returns {Document} Opened document object
 */
function openDocument(documentPath) {
    var docFile = new File(documentPath);

    if (!docFile.exists) {
        throw new Error("Document not found: " + documentPath);
    }

    try {
        var doc = app.open(docFile, false); // false = don't show conversion dialog
        return doc;
    } catch (error) {
        throw new Error("Failed to open document: " + error.message);
    }
}

/**
 * Export document to PDF with current settings
 *
 * @param {Document} doc - InDesign document
 * @param {File} pdfFile - Output PDF file
 * @returns {Object} Export metadata
 */
function exportDocument(doc, pdfFile) {
    var startTime = new Date();

    try {
        // Ensure parent directory exists (InDesign will fail silently otherwise)
        if (!pdfFile.parent.exists) {
            pdfFile.parent.create();
        }

        // Export using current pdfExportPreferences
        doc.exportFile(
            ExportFormat.PDF_TYPE,
            pdfFile,
            false  // showingOptions = false (don't show dialog)
        );

        var endTime = new Date();
        var exportTime = (endTime - startTime) / 1000; // seconds

        // Verify file was created
        if (!pdfFile.exists) {
            throw new Error("PDF file was not created");
        }

        return {
            pageCount: doc.pages.length,
            exportTime: exportTime
        };

    } catch (error) {
        throw new Error("Export failed: " + error.message);
    }
}

/**
 * Apply custom export settings from settings object
 *
 * @param {Document} doc - InDesign document
 * @param {Object} settings - Export settings object
 */
function applyExportSettings(doc, settings) {
    with (app.pdfExportPreferences) {

        // === Standard & Compatibility ===
        if (settings.pdfStandard) {
            try {
                pdfExportPreset = PDFExportPresetList.item(settings.pdfStandard);
            } catch (e) {
                // If preset not found, use default
                pdfExportPreset = PDFExportPresetList.item("[High Quality Print]");
            }
        }

        if (settings.compatibility) {
            acrobatCompatibility = parseAcrobatCompatibility(settings.compatibility);
        }

        // === Color Management ===
        if (settings.colorSpace) {
            colorSpace = parseColorSpace(settings.colorSpace);
        }

        if (settings.outputIntent) {
            outputIntent = settings.outputIntent;
        }

        if (settings.includeIccProfile !== undefined) {
            includeICCProfiles = settings.includeIccProfile;
        }

        if (settings.simulateOverprint !== undefined) {
            simulateOverprint = settings.simulateOverprint;
        }

        // === Image Quality & Compression ===
        if (settings.compression) {
            colorCompression = parseCompression(settings.compression);
            grayscaleCompression = parseCompression(settings.compression);
        }

        if (settings.imageQuality) {
            compressionQuality = parseImageQuality(settings.imageQuality);
        }

        if (settings.jpegQuality !== undefined) {
            jpegQuality = parseJPEGQuality(settings.jpegQuality);
        }

        // Downsampling
        if (settings.downsampleImages !== undefined) {
            if (settings.downsampleImages) {
                colorDownsampling = settings.downsampleColorTo || 300;
                grayscaleDownsampling = settings.downsampleGrayscaleTo || 300;
                monochromeDownsampling = settings.downsampleMonochromeTo || 1200;

                colorDownsamplingDPI = settings.resolutionThreshold || 450;
                grayscaleDownsamplingDPI = settings.resolutionThreshold || 450;
                monochromeDownsamplingDPI = settings.resolutionThreshold || 1800;
            }
        }

        if (settings.resolutionThreshold) {
            thresholdToCompressColor = settings.resolutionThreshold;
            thresholdToCompressGray = settings.resolutionThreshold;
            thresholdToCompressMonochrome = settings.resolutionThreshold;
        }

        // === Marks and Bleeds ===
        if (settings.useDocumentBleed !== undefined) {
            useDocumentBleedWithPDF = settings.useDocumentBleed;
        }

        if (!settings.useDocumentBleed && settings.includeBleed) {
            // Use custom bleed values
            if (settings.bleedTop !== undefined) {
                bleedTop = settings.bleedTop + "mm";
                bleedBottom = settings.bleedBottom + "mm";
                bleedLeft = settings.bleedLeft + "mm";
                bleedRight = settings.bleedRight + "mm";
            }
        }

        // Printer marks
        if (settings.cropMarks !== undefined) {
            cropMarks = settings.cropMarks;
        }
        if (settings.bleedMarks !== undefined) {
            bleedMarks = settings.bleedMarks;
        }
        if (settings.registrationMarks !== undefined) {
            registrationMarks = settings.registrationMarks;
        }
        if (settings.colorBars !== undefined) {
            colorBars = settings.colorBars;
        }
        if (settings.pageInformation !== undefined) {
            pageInformationMarks = settings.pageInformation;
        }

        if (settings.markWeight !== undefined) {
            printerMarkWeight = PDFMarkWeight.P25PT; // Default, can be customized
        }

        // === Page Range ===
        if (settings.pageRange) {
            pageRange = settings.pageRange;
        }

        if (settings.spreads !== undefined) {
            exportReaderSpreads = settings.spreads;
        }

        // === Fonts ===
        if (settings.subsetFontsThreshold !== undefined) {
            subsetFontsBelow = settings.subsetFontsThreshold;
        }

        // === Advanced ===
        if (settings.generateThumbnails !== undefined) {
            generateThumbnails = settings.generateThumbnails;
        }

        if (settings.optimizePdf !== undefined) {
            optimizePDF = settings.optimizePdf;
        }

        if (settings.createTaggedPdf !== undefined) {
            createTaggedPDF = settings.createTaggedPdf;
        }

        if (settings.includeStructure !== undefined) {
            includeStructure = settings.includeStructure;
        }

        if (settings.includeBookmarks !== undefined) {
            includeBookmarks = settings.includeBookmarks;
        }

        if (settings.includeHyperlinks !== undefined) {
            includeHyperlinks = settings.includeHyperlinks;
        }

        if (settings.viewPdfAfterExport !== undefined) {
            viewPDF = settings.viewPdfAfterExport;
        }

        // Transparency flattener
        if (settings.transparencyFlattenerPreset) {
            try {
                appliedFlattenerPreset = app.flattenerPresets.item(
                    settings.transparencyFlattenerPreset
                );
            } catch (e) {
                // Use default if not found
                appliedFlattenerPreset = app.flattenerPresets.item("[High Resolution]");
            }
        }
    }
}

/**
 * Apply default high-quality export settings
 *
 * @param {Document} doc - InDesign document
 */
function applyDefaultSettings(doc) {
    var defaultSettings = {
        pdfStandard: "PDF/X-4:2010",
        colorSpace: "CMYK",
        outputIntent: "Coated FOGRA39 (ISO 12647-2:2004)",
        compression: "JPEG",
        jpegQuality: 12,
        includeBleed: true,
        cropMarks: true,
        registrationMarks: true,
        colorBars: true,
        subsetFontsThreshold: 100,
        optimizePdf: true,
        createTaggedPdf: true
    };

    applyExportSettings(doc, defaultSettings);
}

// === Helper Functions for Parsing Enums ===

function parseColorSpace(colorSpace) {
    switch (colorSpace.toUpperCase()) {
        case "CMYK":
            return ColorSpace.CMYK;
        case "RGB":
            return ColorSpace.RGB;
        case "GRAY":
        case "GRAYSCALE":
            return ColorSpace.GRAY;
        case "UNCHANGED":
            return ColorSpace.UNCHANGED_COLOR_SPACE;
        default:
            return ColorSpace.CMYK;
    }
}

function parseCompression(compression) {
    switch (compression.toUpperCase()) {
        case "JPEG":
            return Compression.JPEG;
        case "ZIP":
            return Compression.ZIP;
        case "JPEG2000":
            return Compression.JPEG_2000_LOSSLESS;
        case "AUTOMATIC":
            return Compression.AUTOMATIC_COMPRESSION;
        case "NONE":
            return Compression.NONE;
        default:
            return Compression.JPEG;
    }
}

function parseImageQuality(quality) {
    switch (quality.toUpperCase()) {
        case "MAXIMUM":
            return CompressionQuality.MAXIMUM;
        case "HIGH":
            return CompressionQuality.HIGH;
        case "MEDIUM":
            return CompressionQuality.MEDIUM;
        case "LOW":
            return CompressionQuality.LOW;
        case "MINIMUM":
            return CompressionQuality.MINIMUM;
        default:
            return CompressionQuality.MAXIMUM;
    }
}

function parseJPEGQuality(quality) {
    // Map 0-12 scale to InDesign JPEGQuality enum
    if (quality >= 11) return JPEGQuality.MAXIMUM;
    if (quality >= 8) return JPEGQuality.HIGH;
    if (quality >= 5) return JPEGQuality.MEDIUM;
    if (quality >= 2) return JPEGQuality.LOW;
    return JPEGQuality.MINIMUM;
}

function parseAcrobatCompatibility(compat) {
    if (compat.indexOf("1.3") !== -1 || compat.indexOf("4") !== -1) {
        return AcrobatCompatibility.ACROBAT_4;
    } else if (compat.indexOf("1.4") !== -1 || compat.indexOf("5") !== -1) {
        return AcrobatCompatibility.ACROBAT_5;
    } else if (compat.indexOf("1.5") !== -1 || compat.indexOf("6") !== -1) {
        return AcrobatCompatibility.ACROBAT_6;
    } else if (compat.indexOf("1.6") !== -1 || compat.indexOf("7") !== -1) {
        return AcrobatCompatibility.ACROBAT_7;
    } else if (compat.indexOf("1.7") !== -1 || compat.indexOf("8") !== -1) {
        return AcrobatCompatibility.ACROBAT_8;
    }
    return AcrobatCompatibility.ACROBAT_7; // Default
}

/**
 * Batch export multiple documents
 *
 * @param {Array} documents - Array of {input, output} objects
 * @param {Object} settings - Shared export settings
 * @returns {Object} Batch export results
 */
function batchExportPDF(documents, settings) {
    var results = {
        total: documents.length,
        succeeded: 0,
        failed: 0,
        exports: []
    };

    for (var i = 0; i < documents.length; i++) {
        var item = documents[i];
        var result = exportToPDFX4(item.input, item.output, settings);

        results.exports.push({
            input: item.input,
            output: item.output,
            success: result.success,
            message: result.message
        });

        if (result.success) {
            results.succeeded++;
        } else {
            results.failed++;
        }
    }

    return results;
}

/**
 * Get current PDF export settings as object
 *
 * @returns {Object} Current export preferences
 */
function getCurrentExportSettings() {
    with (app.pdfExportPreferences) {
        return {
            colorSpace: colorSpace.toString(),
            compression: colorCompression.toString(),
            jpegQuality: jpegQuality.toString(),
            pageRange: pageRange,
            includeBleed: useDocumentBleedWithPDF,
            cropMarks: cropMarks,
            registrationMarks: registrationMarks,
            colorBars: colorBars,
            subsetFontsThreshold: subsetFontsBelow,
            optimizePdf: optimizePDF
        };
    }
}

/**
 * Validate document before export
 *
 * @param {Document} doc - InDesign document
 * @returns {Object} Validation result with warnings
 */
function validateDocument(doc) {
    var warnings = [];
    var errors = [];

    // Check for missing fonts
    var missingFonts = doc.fonts.everyItem().getElements().filter(function(font) {
        return font.status !== FontStatus.INSTALLED;
    });

    if (missingFonts.length > 0) {
        errors.push("Missing fonts: " + missingFonts.length);
    }

    // Check for missing links
    var missingLinks = doc.links.everyItem().getElements().filter(function(link) {
        return link.status === LinkStatus.LINK_MISSING;
    });

    if (missingLinks.length > 0) {
        errors.push("Missing links: " + missingLinks.length);
    }

    // Check for RGB images in CMYK document
    if (doc.cmykProfilePolicy === ColorSettingsPolicy.PRESERVE_EMBEDDED_PROFILES) {
        // Check for RGB graphics
        var rgbImages = doc.allGraphics.everyItem().getElements().filter(function(graphic) {
            try {
                return graphic.space === Space.RGB;
            } catch (e) {
                return false;
            }
        });

        if (rgbImages.length > 0) {
            warnings.push("RGB images found: " + rgbImages.length + " (consider converting to CMYK)");
        }
    }

    // Check for overset text
    var oversetFrames = doc.textFrames.everyItem().getElements().filter(function(frame) {
        return frame.overflows;
    });

    if (oversetFrames.length > 0) {
        warnings.push("Overset text frames: " + oversetFrames.length);
    }

    return {
        isValid: errors.length === 0,
        errors: errors,
        warnings: warnings,
        summary: errors.length === 0 ? "Document valid for export" : "Document has errors"
    };
}

// === Export public API ===
// These functions can be called from Python via JSX runner

var PDFExporter = {
    exportToPDFX4: exportToPDFX4,
    batchExportPDF: batchExportPDF,
    getCurrentExportSettings: getCurrentExportSettings,
    validateDocument: validateDocument
};

// For command-line execution
if (typeof arguments !== 'undefined' && arguments.length > 0) {
    // Called with arguments: indesign_script.jsx documentPath outputPath [settingsJSON]
    var docPath = arguments[0];
    var outPath = arguments[1];
    var settingsJSON = arguments.length > 2 ? arguments[2] : null;

    var settings = null;
    if (settingsJSON) {
        try {
            settings = eval('(' + settingsJSON + ')');
        } catch (e) {
            $.writeln("Error parsing settings JSON: " + e.message);
        }
    }

    var result = exportToPDFX4(docPath, outPath, settings);
    $.writeln(JSON.stringify(result));
}
