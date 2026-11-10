import {rightToolbox} from './right-toolbox.js?v=record-actions-1';
import {initialiseColumns} from './crm-list-columns.js?v=registration-workflow-1';

const form = document.querySelector('form[data-crm-filters]');
if (form) initialiseViews(form);

const operatorLabels = {
    equals: 'is', contains: 'contains', empty: 'is empty', not_empty: 'is not empty',
    less_than: 'is less than', greater_than: 'is greater than', before: 'is before', after: 'is after',
};

function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

function button(text, secondary = false) {
    const node = element('button', 'portal-button' + (secondary ? ' portal-button-secondary' : ''), text);
    node.type = 'button';
    return node;
}

function labelled(text, control) {
    const label = element('label');
    control.setAttribute('aria-label', text);
    label.append(document.createTextNode(text), control);
    return label;
}

export async function initialiseViews(form) {
    const directory = form.dataset.crmFilters;
    const endpoint = form.dataset.viewEndpoint || `/crm/views/${directory}`;
    const catalogueEndpoint = form.dataset.catalogueEndpoint || `/crm/list-preferences/${directory}`;
    const viewPath = form.dataset.viewPath || `/crm/${directory}`;
    const prefix = form.dataset.viewPrefix || '';
    const key = name => prefix + name;
    const quickKey = name => prefix && form.dataset.localSearch && name === 'q' ? key(name) : name;
    const viewQuery = view => {
        const query = new URLSearchParams(prefix ? window.location.search : '');
        query.delete('page');
        if (prefix) {
            for (const name of [...query.keys()]) if(name.startsWith(prefix)) query.delete(name);
            for (const control of form.querySelectorAll('input[name],select[name]')) query.delete(quickKey(control.name));
        }
        query.set(key('view'), view);
        return query;
    };
    const viewFilters = form.querySelector('[data-crm-view-filters]');
    const controls = Array.from(form.querySelectorAll('.review-controls input[name], .review-controls select[name], [data-crm-view-filters] select[name], [data-crm-view-filters] input[name]'));
    const scope = form.querySelector('input[name="mah_id"]')?.value;
    const status = element('p', 'crm-view-status subtle');
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    const bar = element('div', 'crm-view-bar');
    const chooser = element('select');
    chooser.disabled = true;
    chooser.append(new Option('Loading views…', 'all'));
    bar.append(labelled('View', chooser));
    form.prepend(bar);
    bar.append(status);
    let response, catalogue;
    try {
        const results = await Promise.all([
            fetch(endpoint + (endpoint.includes('?') ? '&' + window.location.search.slice(1) : window.location.search)),
            fetch(catalogueEndpoint),
        ]);
        if (!results.every(result => result.ok)) throw new Error();
        [response, catalogue] = await Promise.all(results.map(result => result.json()));
    } catch {
        status.textContent = 'Your views could not be loaded. Reload to try again.';
        return;
    }
    const config = response.config;
    const selected = response.selected;
    if (prefix) for (const control of controls) {
        if (!new URLSearchParams(location.search).has(control.name) && config.quick_filters[control.name] !== undefined) {
            if (control.type === 'checkbox') control.checked = ['true','yes','on','1'].includes(config.quick_filters[control.name]);
            else control.value = config.quick_filters[control.name];
        }
    }
    const currentPreset = response.presets.find(preset => preset.id === new URLSearchParams(window.location.search).get('preset'));
    chooser.replaceChildren(new Option('All records', 'all'));
    if (response.views.length) {
        const group = element('optgroup');
        group.label = 'My views';
        for (const view of response.views) group.append(new Option(view.name + (view.is_default ? ' · default' : ''), String(view.id)));
        chooser.append(group);
    }
    if (response.presets.length) {
        const group = element('optgroup');
        group.label = 'Templates';
        for (const preset of response.presets) group.append(new Option(preset.name, `preset:${preset.id}`));
        chooser.append(group);
    }
    chooser.value = selected ? String(selected.id) : currentPreset ? `preset:${currentPreset.id}` : 'all';
    chooser.disabled = false;
    const fields = catalogue.fields.filter(field => !field.column_only);
    const fieldMap = new Map(fields.map(field => [field.key, field]));
    const headers = Array.from(form.closest('section').querySelectorAll('table[data-crm-columns] thead th'));
    const standardOrder = headers.map(header => header.dataset.column);
    const standardColumns = headers.filter(header => header.dataset.defaultVisible !== 'false').map(header => header.dataset.column);
    form.dispatchEvent(new CustomEvent('portal-view-config', {detail: {config, schema: catalogue.fields, server: response.server_filtered}}));
    const columns = initialiseColumns(form, config);
    // Place view settings and conditions ahead of the column editor.
    const conditionsPanel = element('details', 'crm-filter-settings crm-view-conditions');
    conditionsPanel.append(element('summary', '', 'Conditions & sorting'));
    if (viewFilters) {
        conditionsPanel.append(viewFilters.querySelector('.crm-view-sorting'));
        viewFilters.remove();
    }
    conditionsPanel.append(element('p', 'subtle', 'Records must match every condition (AND). Imported fields retain their source text.'));
    const conditionList = element('div', 'crm-condition-list');
    const conditionRows = [];
    conditionsPanel.append(conditionList);
    function addCondition(initial = {}) {
        if (conditionRows.length >= 12) {
            status.textContent = 'Use up to 12 conditions.';
            return;
        }
        const row = element('div', 'crm-condition-row');
        const fieldSelect = element('select');
        fieldSelect.setAttribute('aria-label', 'Condition field');
        for (const field of fields) fieldSelect.append(new Option(field.label + (field.origin === 'Airtable import' ? ' · imported' : ''), field.key));
        fieldSelect.value = initial.field || fields[0].key;
        const operator = element('select');
        operator.setAttribute('aria-label', 'Condition operator');
        const valueContainer = element('div', 'crm-condition-value');
        let valueInput;
        function updateValue(value = '') {
            const field = fieldMap.get(fieldSelect.value);
            if (field.type === 'boolean') {
                valueInput = element('select');
                valueInput.append(new Option('Yes', 'true'), new Option('No', 'false'));
                valueInput.value = value === false || value === 'false' ? 'false' : 'true';
            } else {
                valueInput = element('input');
                valueInput.type = field.type === 'number' ? 'number' : field.type === 'date' ? 'date' : 'text';
                if (field.type === 'number') valueInput.step = 'any';
                valueInput.maxLength = 500;
                valueInput.value = value;
            }
            valueInput.setAttribute('aria-label', 'Condition value');
            valueContainer.replaceChildren(valueInput);
            valueContainer.hidden = ['empty', 'not_empty'].includes(operator.value);
        }
        function updateField(initialOperator, value = '') {
            const field = fieldMap.get(fieldSelect.value);
            operator.replaceChildren(...field.operators.map(op => new Option(field.type === 'list' && op === 'contains' ? 'includes' : operatorLabels[op], op)));
            if (field.operators.includes(initialOperator)) operator.value = initialOperator;
            updateValue(value);
        }
        updateField(initial.operator, initial.value ?? '');
        fieldSelect.addEventListener('change', () => updateField(''));
        operator.addEventListener('change', () => valueContainer.hidden = ['empty', 'not_empty'].includes(operator.value));
        const remove = button('Remove', true);
        remove.setAttribute('aria-label', 'Remove condition');
        const entry = {getValue: () => ({field: fieldSelect.value, operator: operator.value, value: valueInput.value})};
        remove.addEventListener('click', () => {
            conditionRows.splice(conditionRows.indexOf(entry), 1);
            row.remove();
            form.dispatchEvent(new CustomEvent('crm-view-change'));
        });
        row.append(fieldSelect, operator, valueContainer, remove);
        conditionList.append(row);
        conditionRows.push(entry);
        form.dispatchEvent(new CustomEvent('crm-view-change'));
    }
    for (const condition of config.conditions) addCondition(condition);
    const add = button('Add condition', true);
    add.addEventListener('click', () => addCondition());
    conditionsPanel.append(add);
    const sorting = element('div', 'crm-view-sorting');
    const sort = element('select');
    sort.append(new Option('Directory order', ''));
    for (const field of fields) sort.append(new Option(field.label + (field.origin === 'Airtable import' ? ' · imported' : ''), field.key));
    sort.value = config.sort;
    const direction = element('select');
    direction.append(new Option('Ascending', 'asc'), new Option('Descending', 'desc'));
    direction.value = config.direction;
    sorting.append(labelled('Sort by', sort), labelled('Direction', direction));
    const apply = button('Apply');
    apply.addEventListener('click', () => applyCurrent());
    conditionsPanel.append(sorting);
    const settings = element('details', 'crm-filter-settings crm-view-settings');
    settings.append(element('summary', '', 'Save & manage views'));
    const name = element('input');
    name.type = 'text';
    name.maxLength = 80;
    name.value = selected?.name || currentPreset?.name || '';
    name.placeholder = 'e.g. MAHs without a signed agreement';
    const makeDefault = element('input');
    makeDefault.type = 'checkbox';
    makeDefault.checked = Boolean(selected?.is_default);
    const defaultLabel = labelled('Use as my default for this directory', makeDefault);
    defaultLabel.className = 'resolve-confirm';
    settings.append(labelled('View name', name), defaultLabel);
    const actions = element('div', 'crm-filter-actions');
    const save = button('Save view');
    const create = button('Save as new view', true);
    const removeView = button('Delete view', true);
    save.disabled = create.disabled = !response.available;
    removeView.disabled = !response.available || !selected;
    actions.append(save, create, removeView);
    settings.append(actions);
    if (!response.available) settings.append(element('p', 'subtle', 'Sign in to save personal views.'));
    const columnsPanel = form.querySelector('details:has(.crm-column-options)');
    const resultPanel = form.closest('section');
    resultPanel.classList.add('crm-list-workspace');
    form.classList.add('crm-toolbox-enabled');
    // Keep only direct search in the compact toolbar. All other scope controls
    // belong to the view and are moved without losing their saved values.
    const quick = form.querySelector('.review-controls');
    const extraScope = element('div', 'crm-view-sorting');
    for (const label of Array.from(quick.querySelectorAll(':scope > label'))) {
        if (!label.querySelector('[name="q"]')) extraScope.append(label);
    }
    if (extraScope.childElementCount) conditionsPanel.prepend(extraScope);
    const search = quick.querySelector('button[type="submit"]');
    if (search) search.textContent = 'Search';
    bar.append(quick);
    const configure = button('Configure view', true);
    configure.setAttribute('aria-expanded', 'false');
    const toolboxId = prefix ? 'view-toolbox-' + directory : 'crm-view-toolbox';
    configure.setAttribute('aria-controls', toolboxId);
    bar.append(configure, status);
    const toolbox = element('aside', 'crm-view-toolbox');
    toolbox.id = toolboxId;
    toolbox.hidden = true;
    toolbox.setAttribute('aria-label', 'Configure view');
    const toolboxHeading = element('div', 'crm-toolbox-heading');
    const close = button('Close', true);
    close.setAttribute('aria-label', 'Close view toolbox');
    toolboxHeading.append(element('h2', '', 'View toolbox'), close);
    const tabs = element('div', 'crm-toolbox-tabs');
    tabs.setAttribute('role', 'tablist');
    tabs.setAttribute('aria-label', 'View configuration');
    const tabButtons = [];
    const panels = [];
    let activeTab = 'conditions';
    for (const [key, title, original] of [
        ['conditions', 'Conditions', conditionsPanel],
        ['columns', 'Columns', columnsPanel],
        ['save', 'Save view', settings],
    ]) {
        const tab = button(title, true);
        tab.id = `${toolboxId}-tab-${key}`;
        tab.dataset.tab = key;
        tab.setAttribute('role', 'tab');
        tab.setAttribute('aria-controls', `${toolboxId}-panel-${key}`);
        const panel = element('div', `crm-toolbox-panel crm-toolbox-${key}`);
        panel.id = `${toolboxId}-panel-${key}`;
        panel.setAttribute('role', 'tabpanel');
        panel.setAttribute('aria-labelledby', tab.id);
        for (const node of Array.from(original.children)) {
            if (node.tagName !== 'SUMMARY') panel.append(node);
        }
        original.remove();
        tab.addEventListener('click', () => activateTab(key));
        tab.addEventListener('keydown', event => {
            const index = tabButtons.indexOf(tab);
            const destination = event.key === 'ArrowRight' ? (index + 1) % 3
                : event.key === 'ArrowLeft' ? (index + 2) % 3
                : event.key === 'Home' ? 0 : event.key === 'End' ? 2 : null;
            if (destination === null) return;
            event.preventDefault();
            activateTab(tabButtons[destination].dataset.tab);
            tabButtons[destination].focus();
        });
        tabButtons.push(tab);
        panels.push(panel);
        tabs.append(tab);
    }
    const toolboxBody = element('div', 'crm-toolbox-body');
    toolboxBody.append(...panels);
    const footer = element('div', 'crm-toolbox-footer');
    footer.append(apply, element('span', 'subtle', 'Apply previews the list. Save view keeps your configuration.'));
    toolbox.append(toolboxHeading, tabs, toolboxBody, footer);
    const backdrop = button('Close view toolbox');
    backdrop.className = 'crm-toolbox-backdrop';
    backdrop.setAttribute('aria-label', 'Close view toolbox');
    backdrop.textContent = '';
    backdrop.tabIndex = -1;
    backdrop.hidden = true;
    form.append(backdrop, toolbox);
    const toolboxStatus = element('p', 'crm-view-status');
    toolboxStatus.setAttribute('role', 'status');
    footer.append(toolboxStatus);
    new MutationObserver(() => { toolboxStatus.textContent = status.textContent; })
        .observe(status, {childList: true, characterData: true, subtree: true});
    function activateTab(key) {
        activeTab = key;
        for (let index = 0; index < tabButtons.length; index++) {
            const selected = tabButtons[index].dataset.tab === key;
            tabButtons[index].setAttribute('aria-selected', String(selected));
            tabButtons[index].tabIndex = selected ? 0 : -1;
            panels[index].hidden = !selected;
        }
    }
    const toolboxController = rightToolbox({
        toolbox, opener: configure, close, backdrop, workspace: resultPanel,
        initialFocus: () => tabButtons.find(tab => tab.dataset.tab === activeTab),
    });
    function showToolbox(key = activeTab, focus = true) {
        activateTab(key);
        toolboxController.show(focus);
    }
    const resumeKey = `crm-toolbox-resume:${directory}`;
    function rememberToolbox() {
        try { if (!toolbox.hidden) sessionStorage.setItem(resumeKey, activeTab); } catch {}
    }
    activateTab('conditions');
    try {
        const resume = sessionStorage.getItem(resumeKey);
        sessionStorage.removeItem(resumeKey);
        if (['conditions', 'columns', 'save'].includes(resume)) showToolbox(resume, false);
    } catch {}

    function currentConfig() {
        return {
            quick_filters: Object.fromEntries(controls.map(control => [control.name, control.type === 'checkbox' ? control.checked ? control.value : '' : control.value])),
            conditions: conditionRows.map(row => row.getValue()),
            sort: sort.value, direction: direction.value,
            ...columns.getState(),
        };
    }
    function navigate(configuration, view = selected ? String(selected.id) : 'all', preset = '') {
        const query = viewQuery(view);
        if (scope) query.set('mah_id', scope);
        for (const [name, value] of Object.entries(configuration.quick_filters || {})) {
            const control = controls.find(control => control.name === name);
            // An unchecked checkbox must explicitly override a saved view's true value.
            query.set(quickKey(name), control?.type === 'checkbox' && value === '' ? 'false' : value);
        }
        if (preset) query.set(key('preset'), preset);
        if (configuration.conditions) query.set(key('rules'), JSON.stringify(configuration.conditions));
        if (configuration.columns || configuration.column_order) query.set(key('layout'), JSON.stringify({columns: configuration.columns, column_order: configuration.column_order}));
        if (configuration.sort !== undefined) query.set(key('sort'), configuration.sort);
        if (configuration.direction) query.set(key('direction'), configuration.direction);
        if (query.toString().length > 12000) {
            status.textContent = 'Save this view to apply these conditions.';
            showToolbox('save');
            return;
        }
        rememberToolbox();
        window.location.assign(`${viewPath}?${query}`);
    }
    async function post(command) {
        const body = new URLSearchParams({
            command, name: name.value, is_default: String(makeDefault.checked),
            config: JSON.stringify(currentConfig()),
        });
        if (selected && command !== 'create') {
            body.set('id', String(selected.id));
            body.set('version', String(selected.version));
        }
        const result = await fetch(endpoint, {method: 'POST', body});
        const data = await result.json().catch(() => null);
        if (!result.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : 'The view could not be saved. Try again.');
        return data;
    }
    async function applyCurrent() {
        apply.disabled = true;
        status.textContent = 'Applying conditions…';
        try {
            const data = await post('preview');
            navigate(data.config);
        } catch (error) {
            status.textContent = error.message;
        } finally {
            apply.disabled = false;
        }
    }
    form.addEventListener('submit', event => {
        event.preventDefault();
        applyCurrent();
    });
    async function persist(command) {
        save.disabled = create.disabled = removeView.disabled = true;
        status.textContent = 'Saving view…';
        try {
            const data = await post(command);
            const query = viewQuery(data.view ? String(data.view.id) : 'all');
            if (scope) query.set('mah_id', scope);
            rememberToolbox();
            window.location.assign(`${viewPath}?${query}`);
        } catch (error) {
            status.textContent = error.message;
            showToolbox('save');
            save.disabled = create.disabled = !response.available;
            removeView.disabled = !selected;
        }
    }
    save.addEventListener('click', () => persist(selected ? 'save' : 'create'));
    create.addEventListener('click', () => persist('create'));
    removeView.addEventListener('click', () => {
        if (window.confirm('Delete this personal view?')) persist('delete');
    });
    chooser.addEventListener('change', () => {
        const value = chooser.value;
        if (value.startsWith('preset:')) {
            const preset = response.presets.find(item => `preset:${item.id}` === value);
            navigate({quick_filters: {}, conditions: [], sort: '', direction: 'asc', ...preset.config}, 'all', preset.id);
        } else if (value === 'all') {
            navigate({quick_filters: {}, conditions: [], sort: '', direction: 'asc'}, 'all');
        } else {
            const query = viewQuery(value);
            if (scope) query.set('mah_id', scope);
            rememberToolbox();
            window.location.assign(`${viewPath}?${query}`);
        }
    });
    function markUnsaved(event) {
        if (event.target.closest?.('.crm-column-search')) return;
        status.textContent = 'Unsaved changes';
        status.title = 'Apply to preview, or save the view.';
    }
    form.addEventListener('input', markUnsaved);
    form.addEventListener('change', markUnsaved);
    form.addEventListener('crm-view-change', markUnsaved);
    function signature(value) {
        return JSON.stringify({
            quick: Object.entries(value.quick_filters || {}).sort(),
            conditions: value.conditions, sort: value.sort, direction: value.direction,
            columns: value.columns || standardColumns, order: value.column_order || standardOrder,
        });
    }
    if (selected && signature(config) !== signature(selected.config)) {
        status.textContent = 'Unsaved changes';
    } else if (currentPreset) {
        status.textContent = 'Template applied. Save it as a personal view.';
    }
}
