#target "InDesign"
/*
Export active document to IDML (for CAT tools), then to PDF/X-4.
*/
(function(){
    if (app.documents.length === 0) { alert("Open a document."); return; }
    var doc = app.activeDocument;
    var base = File.saveDialog("Choose folder to export IDML/PDF");
    if (!base) return;
    var idml = File(base + "/" + doc.name.replace(/\.indd$/i,"") + ".idml");
    doc.exportFile(ExportFormat.INDESIGN_MARKUP, idml);
    // Export PDF/X-4
    var pdf = File(base + "/" + doc.name.replace(/\.indd$/i,"") + "-X4.pdf");
    var preset = app.pdfExportPresets.itemByName("PDF/X-4:2008");
    doc.exportFile(ExportFormat.PDF_TYPE, pdf, false, preset);
    alert("Exported:\\n" + idml.fsName + "\\n" + pdf.fsName);
})();
