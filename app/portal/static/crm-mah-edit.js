const cards = document.querySelector("[data-mah-cards]");
const pendingCards = new WeakSet();
const recordSteps = document.querySelector(".record-navigation-steps");

async function updateCard(card, url, fields, pending, saving = false) {
    if (pendingCards.has(card)) return;
    pendingCards.add(card);
    card.dataset.mahPending = 'true';
    document.dispatchEvent(new Event('crm-record-edit-state'));
    const status = card.querySelector("[data-mah-status]");
    status.hidden = false;
    status.textContent = pending;
    const editorFields = saving ? card.querySelector("fieldset[data-mah-editor]") : null;
    const active = document.activeElement;
    if (editorFields) editorFields.disabled = true;
    try {
        const response = await fetch(url, fields ? { method: "POST", body: fields } : {});
        if (!response.ok) {
            const error = await response.json().catch(() => null);
            throw new Error(typeof error?.detail === "string" ? error.detail : "");
        }
        const page = new DOMParser().parseFromString(await response.text(), "text/html");
        const section = card.dataset.mahCard;
        const nextCard = page.querySelector(`[data-mah-card="${section}"]`);
        if (!nextCard) throw new Error("Reload the page and sign in if needed.");

        const editor = nextCard.closest("form");
        if (editor) {
            const form = document.createElement("form");
            form.method = "post";
            form.setAttribute("action", editor.getAttribute("action"));
            form.className = "review-form";
            for (const name of ["version", "section"]) {
                form.append(editor.querySelector(`input[name="${name}"]`).cloneNode());
            }
            const fieldset = document.createElement("fieldset");
            fieldset.className = "analysis-edit-fields mah-profile";
            fieldset.dataset.mahEditor = "";
            const nextStatus = nextCard.querySelector("[data-mah-status]");
            fieldset.append(...Array.from(nextCard.childNodes).filter(node => node !== nextStatus));
            form.append(fieldset);
            nextCard.append(form);
        }

        if (saving) {
            for (const selector of ['form:has(button[value="archive"])', 'form[action$="/transfer"]']) {
                const input = selector + ' input[name="version"]';
                const savedVersion = page.querySelector(input);
                const currentVersion = document.querySelector(input);
                if (savedVersion && currentVersion) currentVersion.value = savedVersion.value;
            }
            if (section === "general") {
                document.querySelector(".mah-title").replaceWith(page.querySelector(".mah-title"));
                document.title = page.title;
            }
            if (section === "invoice") {
                const invoiceEmail = cards.querySelector("[data-mah-invoice-email]");
                const savedEmail = page.querySelector("[data-mah-invoice-email]");
                if (invoiceEmail && savedEmail) invoiceEmail.textContent = savedEmail.textContent;
            }
        }

        const shouldFocus = card.contains(document.activeElement)
            || (card.contains(active) && document.activeElement === document.body);
        card.replaceChildren(...nextCard.childNodes);
        // Refresh neighbours from the returned read view (renaming can change
        // list order). Keep the same container for the Actions/navigation code.
        if (!cards.querySelector('[data-mah-editor]') && recordSteps) {
            const refreshedSteps = page.querySelector('.record-navigation-steps');
            if (refreshedSteps) recordSteps.replaceChildren(...refreshedSteps.childNodes);
        }
        document.dispatchEvent(new Event('crm-record-edit-state'));
        if (section === "contacts") window.initContactPickers(card);
        if (shouldFocus) {
            card.querySelector('textarea, input:not([type="hidden"]), select, [data-open-contact-picker], .preview-label')
                ?.focus({ preventScroll: true });
        }
    } catch (error) {
        status.textContent = error.message || "The request failed. Try again.";
    } finally {
        if (editorFields) editorFields.disabled = false;
        pendingCards.delete(card);
        delete card.dataset.mahPending;
        document.dispatchEvent(new Event('crm-record-edit-state'));
    }
}

cards.addEventListener("click", event => {
    const link = event.target.closest(".preview-label, .mah-edit-actions a");
    const card = link?.closest("[data-mah-card]");
    if (!card || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    updateCard(card, link.href, null, "Loading…");
});

cards.addEventListener("submit", event => {
    const form = event.target;
    const card = form.closest("[data-mah-card]");
    if (!card) return;
    event.preventDefault();
    const drafting = Boolean(form.querySelector('input[name="action"][value="draft"]'));
    updateCard(
        card,
        form.getAttribute("action"),
        new URLSearchParams(new FormData(form, event.submitter)),
        drafting ? "Researching public sources…" : "Saving changes…",
        !drafting,
    );
});
