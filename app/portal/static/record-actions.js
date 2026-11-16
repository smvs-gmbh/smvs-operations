import {rightToolbox} from './right-toolbox.js?v=mah-actions-1';

const source = document.querySelector('[data-record-actions]');
const workspace = source?.closest('[data-record-workspace]');
const navigation = document.querySelector('.record-navigation');
if (workspace && navigation) initialiseRecordActions();

function button(text, label = '') {
    const node = document.createElement('button');
    node.type = 'button';
    node.className = 'portal-button portal-button-secondary';
    node.textContent = text;
    if (label) node.setAttribute('aria-label', label);
    return node;
}
function initialiseRecordActions() {
    const opener = button('Actions');
    opener.setAttribute('aria-controls', 'record-actions-toolbox');
    opener.setAttribute('aria-expanded', 'false');
    const tools = document.createElement('div');
    tools.className = 'record-navigation-tools';
    const steps = navigation.querySelector('.record-navigation-steps');
    if (steps) tools.append(steps);
    tools.append(opener);
    navigation.append(tools);

    const toolbox = document.createElement('aside');
    toolbox.id = 'record-actions-toolbox';
    toolbox.className = 'crm-view-toolbox record-actions-toolbox';
    toolbox.hidden = true;
    toolbox.setAttribute('aria-label', 'Record actions');
    const header = document.createElement('div');
    header.className = 'crm-toolbox-heading';
    const title = document.createElement('h2');
    title.textContent = 'Actions';
    const close = button('Close', 'Close actions toolbox');
    if (source.hasAttribute('data-crm-actions')) {
        toolbox.classList.add('crm-actions');
        const heading = document.createElement('div');
        const recordName = document.createElement('small');
        recordName.textContent = source.dataset.crmActions;
        heading.append(title, recordName);
        const controls = document.createElement('div');
        controls.className = 'crm-actions-controls';
        const help = document.createElement('a');
        help.className = 'portal-button portal-button-secondary';
        help.href = '/user-guide';
        help.textContent = '?';
        help.setAttribute('aria-label', 'Open the User Guide');
        controls.append(help, close);
        header.append(heading, controls);
    } else {
        header.append(title, close);
    }
    const body = document.createElement('div');
    body.className = 'crm-toolbox-body review-form';
    const actions = source.querySelector('details');
    for (const node of Array.from(actions.childNodes)) {
        if (node.nodeName !== 'SUMMARY') body.append(node);
    }
    toolbox.append(header, body);
    const backdrop = button('', 'Close actions toolbox');
    backdrop.className = 'crm-toolbox-backdrop';
    backdrop.tabIndex = -1;
    backdrop.hidden = true;
    workspace.append(backdrop, toolbox);
    source.remove();
    const controller = rightToolbox({toolbox, opener, close, backdrop, workspace});
    if (toolbox.classList.contains('crm-actions')) {
        body.querySelectorAll('[data-note-apply]').forEach(node => { node.hidden = true; });
        body.addEventListener('change', event => {
            if (event.target.matches('[data-note-choice]')) event.target.form.requestSubmit();
        });
        body.addEventListener('click', event => {
            const link = event.target.closest('[data-action-jump]');
            if (!link || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            controller.hide(false);
            document.getElementById(link.hash.slice(1))?.focus({preventScroll: true});
        });
        if (new URLSearchParams(location.search).get('actions') === 'notes') {
            controller.show();
        }
    }

    // MAH card editing happens without a page reload. Avoid simultaneous
    // record actions while a card has an unsaved editor on the same record.
    const cards = document.querySelector('[data-mah-cards]');
    if (cards) {
        new MutationObserver(() => {
            const editing = Boolean(cards.querySelector('[data-mah-editor]'));
            opener.disabled = editing;
            opener.title = editing ? 'Finish editing the section to use record actions.' : '';
            if (editing && !toolbox.hidden) controller.hide(false);
        }).observe(cards, {childList: true, subtree: true});
    }
}
