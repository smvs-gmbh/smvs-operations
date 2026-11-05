"use strict";

(() => {
    const storageKey = "smvs-text-size";
    const min = 90;
    const max = 140;
    const step = 10;
    let size = 100;

    try {
        const stored = Number(localStorage.getItem(storageKey));
        if (stored >= min && stored <= max && stored % step === 0) size = stored;
    } catch {
        // Text size still works for the current page when storage is unavailable.
    }

    const applySize = () => {
        document.documentElement.style.fontSize = size + "%";
    };
    applySize();

    document.addEventListener("DOMContentLoaded", () => {
        const controls = document.getElementById("text-size-controls");
        const decrease = document.getElementById("text-size-decrease");
        const increase = document.getElementById("text-size-increase");
        const value = document.getElementById("text-size-value");
        if (!controls || !decrease || !increase || !value) return;

        function updateControls() {
            value.textContent = size + "%";
            decrease.disabled = size <= min;
            increase.disabled = size >= max;
        }

        function changeSize(delta) {
            size = Math.min(max, Math.max(min, size + delta));
            applySize();
            updateControls();
            try {
                localStorage.setItem(storageKey, String(size));
            } catch {
                // Storage can be disabled in the browser.
            }
        }

        decrease.addEventListener("click", () => changeSize(-step));
        increase.addEventListener("click", () => changeSize(step));
        updateControls();
        controls.hidden = false;
    });
})();
