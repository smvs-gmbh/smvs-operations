// CRM review shortcuts use existing list/detail URLs, preserving view scope.
const navigation = document.querySelector('.record-navigation');
const crmNavigation = document.querySelector('.crm-nav');
const cards = document.querySelector('[data-mah-cards]');
const dirtyForms = new Set();

function editing() {
    for (const form of dirtyForms) if (!form.isConnected) dirtyForms.delete(form);
    return dirtyForms.size > 0 || navigation?.dataset.recordEditing === 'true'
        || Boolean(document.querySelector('[data-mah-editor], [data-mah-pending]'));
}
function updateRecordNavigation() {
    if (!navigation) return;
    const busy = editing();
    const steps = navigation.querySelector('.record-navigation-steps');
    if (steps) steps.hidden = false;
    for (const link of navigation.querySelectorAll('[data-record-href]')) {
        if (busy) {
            link.removeAttribute('href');
            link.setAttribute('aria-disabled', 'true');
            link.tabIndex = -1;
            link.title = 'Save or cancel your changes to switch records.';
        } else {
            link.href = link.dataset.recordHref;
            link.removeAttribute('aria-disabled');
            link.removeAttribute('tabindex');
            link.title = link.rel === 'next' ? 'Next record · Alt+Shift+Right' : 'Previous record · Alt+Shift+Left';
        }
    }
}
if (cards) new MutationObserver(updateRecordNavigation)
    .observe(cards, {childList: true, subtree: true, attributes: true, attributeFilter: ['data-mah-pending']});
for (const type of ['input', 'change']) document.addEventListener(type, event => {
    const form = event.target.closest?.('form');
    if (form?.method.toLowerCase() === 'post' && !form.closest('.crm-view-toolbox')) {
        dirtyForms.add(form);
        updateRecordNavigation();
    }
});
document.addEventListener('crm-record-edit-state', updateRecordNavigation);
updateRecordNavigation();

if (navigation) navigation.querySelector('[data-record-back]')?.setAttribute('title', 'Back to list · Alt+Shift+Up');

const shortcuts = [
    ['Alt+Shift+Right', 'Next record'],
    ['Alt+Shift+Left', 'Previous record'],
    ['Alt+Shift+Down', 'Next CRM tab'],
    ['Alt+Shift+Up', 'Back to list'],
];
const help = document.createElement('dialog');
help.className = 'crm-shortcut-help';
help.setAttribute('aria-labelledby', 'crm-shortcut-title');
const heading = document.createElement('h2');
heading.id = 'crm-shortcut-title';
heading.textContent = 'Keyboard shortcuts';
const description = document.createElement('p');
description.textContent = 'Use Alt (Option on Mac) + Shift and an arrow key. Shortcuts are paused in input fields, during section editing and while a toolbox or dialog is open.';
const list = document.createElement('dl');
for (const [keys, label] of shortcuts) {
    const term = document.createElement('dt');
    term.textContent = label;
    const value = document.createElement('dd');
    const key = document.createElement('kbd');
    key.textContent = keys;
    value.append(key);
    list.append(term, value);
}
const close = document.createElement('button');
close.type = 'button';
close.className = 'portal-button portal-button-secondary';
close.textContent = 'Close';
close.addEventListener('click', () => help.close());
help.append(heading, description, list, close);
document.body.append(help);
const helpButton = document.createElement('button');
helpButton.type = 'button';
helpButton.className = 'portal-button portal-button-secondary crm-shortcut-button';
helpButton.textContent = 'Shortcuts';
helpButton.setAttribute('aria-label', 'Keyboard shortcuts');
helpButton.setAttribute('aria-haspopup', 'dialog');
helpButton.addEventListener('click', () => help.showModal());
(navigation?.querySelector('.record-navigation-tools') || navigation || crmNavigation)?.append(helpButton);

function editableTarget(target) {
    return target instanceof Element && Boolean(target.closest(
        'input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"], [role="combobox"]'
    ));
}
document.addEventListener('keydown', event => {
    if (event.defaultPrevented || event.repeat || event.isComposing
        || !event.altKey || !event.shiftKey || event.ctrlKey || event.metaKey
        || editableTarget(event.target) || editing()
        || document.querySelector('dialog[open], .crm-view-toolbox:not([hidden]), [aria-modal="true"]')) return;
    let link;
    switch (event.key) {
    case 'ArrowRight': link = navigation?.querySelector('a[rel="next"][href]'); break;
    case 'ArrowLeft': link = navigation?.querySelector('a[rel="prev"][href]'); break;
    case 'ArrowUp': link = navigation?.querySelector('[data-record-back][href]'); break;
    case 'ArrowDown': {
        const tabs = Array.from(crmNavigation?.querySelectorAll('a[href]') || []);
        const index = tabs.findIndex(tab => tab.hasAttribute('aria-current'));
        if (index >= 0) link = tabs[(index + 1) % tabs.length];
        break;
    }
    default: return;
    }
    // Consume recognised review shortcuts at list boundaries as well.
    event.preventDefault();
    if (link && link.getAttribute('aria-disabled') !== 'true') link.click();
});
