#target "InDesign"
/*
Anchors all rectangles with label "figure" inline at the nearest insertion point
and applies the "Figure Inline" Object Style if present.
*/
(function(){
    if (app.documents.length === 0) { alert("Open a document."); return; }
    var doc = app.activeDocument;
    var objStyle = null;
    try { objStyle = doc.objectStyles.itemByName("Figure Inline"); } catch(e) {}
    var items = doc.allPageItems;
    for (var i=0; i<items.length; i++) {
        var it = items[i];
        if (it instanceof Rectangle && it.label === "figure") {
            var story = it.parentStory;
            var ip = story.insertionPoints[-1];
            try {
                it.anchoredObjectSettings.anchoredPosition = AnchorPosition.INLINE_POSITION;
                it.anchoredObjectSettings.anchorYoffset = 0;
                if (objStyle) it.appliedObjectStyle = objStyle;
            } catch(e) {}
        }
    }
    alert("Anchoring finished.");
})();
