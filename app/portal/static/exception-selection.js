"use strict";

const actionsForm = document.getElementById("exception-actions-form");
const selectPage = document.getElementById("select-page-exceptions");

if (actionsForm && selectPage) {
    const rows = Array.from(actionsForm.elements).filter(
        element => element.matches('input[type="checkbox"][name^="target_"]:enabled')
    );
    const count = document.getElementById("exception-selection-count");
    const previewButton = document.getElementById("preview-selected-rule");
    const reopenButton = document.getElementById("reopen-selected-exceptions");

    function updatePageSelection() {
        const selected = rows.filter(row => row.checked).length;
        selectPage.checked = selected === rows.length;
        selectPage.indeterminate = selected > 0 && selected < rows.length;
        count.textContent = selected + " selected on this page";
        if (previewButton) previewButton.disabled = selected === 0;
        if (reopenButton) {
            reopenButton.disabled = selected === 0 || rows.some(row => row.checked && row.dataset.resolved !== "yes");
        }
    }

    if (rows.length) {
        selectPage.hidden = false;
        selectPage.addEventListener("change", () => {
            rows.forEach(row => { row.checked = selectPage.checked; });
            updatePageSelection();
        });
        rows.forEach(row => row.addEventListener("change", updatePageSelection));
        window.addEventListener("pageshow", updatePageSelection);
        updatePageSelection();
    }
}
