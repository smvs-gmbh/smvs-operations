// Typed relation editors share behaviour but retain independent selections and outputs.
const operatorLabels = {
    equals: 'is', not_equals: 'is not', greater_than: '>', greater_equal: '≥',
    less_than: '<', less_equal: '≤', contains: 'contains', empty: 'is empty', not_empty: 'is not empty',
};
const definitions = [
    {
        key: 'declaration_lookup', title: 'Self-declarations', prefix: 'sd_', defaultField: 'sd_year',
        labels: {sd_year: 'SD year', sd_packs: 'RX packs sold', sd_sales_group: 'RX sales group', sd_status: 'Declaration status', sd_declaration: 'Declaration', sd_selection: 'Selection result'},
        types: {sd_year: 'number', sd_packs: 'number', sd_sales_group: 'text', sd_status: 'text'},
        selectionFields: ['sd_year', 'sd_packs'],
        hint: 'Duplicate MAH/year records are data errors. The highest year does not establish receipt or approval.',
    },
    {
        key: 'agreement_lookup', title: 'Agreements', prefix: 'ag_', defaultField: 'ag_status',
        labels: {ag_contract_id: 'Contract ID', ag_contractor: 'Contractor', ag_status: 'Contract status', ag_signing_date: 'Signing date', ag_start_date: 'Start date · imported', ag_termination_date: 'Termination date · imported', ag_selection: 'Selection result'},
        types: {ag_contract_id: 'text', ag_contractor: 'text', ag_status: 'text', ag_signing_date: 'date', ag_start_date: 'text', ag_termination_date: 'text'},
        selectionFields: ['ag_signing_date'],
        hint: 'Several linked agreements are allowed. Signing date alone does not establish whether a contract is in force. Imported start/termination dates retain their source text.',
    },
];
function node(tag, text = '') {
    const result = document.createElement(tag);
    result.textContent = text;
    return result;
}
function select(items, value, label) {
    const result = node('select');
    for (const [key, text] of items) result.append(new Option(text, key));
    result.value = value;
    result.setAttribute('aria-label', label);
    return result;
}
function labelled(text, control) {
    const result = node('label', text);
    result.append(control);
    return result;
}
function button(text) {
    const result = node('button', text);
    result.type = 'button';
    result.className = 'portal-button portal-button-secondary';
    return result;
}
function relationEditor(form, definition, initial, changed) {
    const {title, labels, types, selectionFields} = definition;
    const panel = node('section');
    panel.dataset.lookupRelation = definition.key;
    panel.className = 'crm-relation-editor';
    panel.append(node('h3', title));
    const note = node('p', 'Conditions filter the related records of each MAH. All outputs come from one selected record.');
    note.className = 'subtle';
    panel.append(note);
    const join = select([['and', 'All conditions (AND)'], ['or', 'Any condition (OR)']], initial.match, `${title}: Match lookup conditions`);
    panel.append(labelled('Match', join));
    const list = node('div');
    list.className = 'crm-condition-list';
    panel.append(list);
    const entries = [];
    function addCondition(initial = {field: definition.defaultField, operator: 'equals', value: ''}) {
        if (entries.length >= 8) return;
        const row = node('div');
        row.className = 'crm-condition-row';
        const field = select(Object.keys(types).map(key => [key, labels[key]]), initial.field, `${title}: Lookup condition field`);
        const operator = select([], null, `${title}: Lookup condition operator`);
        const container = node('div');
        container.className = 'crm-condition-value';
        const input = node('input');
        input.setAttribute('aria-label', `${title}: Lookup condition value`);
        input.maxLength = 200;
        container.append(input);
        function showValue() {
            container.hidden = ['empty', 'not_empty'].includes(operator.value);
            input.disabled = container.hidden;
            input.required = !container.hidden;
        }
        function update(op, value) {
            const typed = ['number', 'date'].includes(types[field.value]);
            const keys = typed
                ? ['equals', 'not_equals', 'greater_than', 'greater_equal', 'less_than', 'less_equal', 'empty', 'not_empty']
                : ['equals', 'not_equals', 'contains', 'empty', 'not_empty'];
            operator.replaceChildren(...keys.map(key => new Option(operatorLabels[key], key)));
            operator.value = keys.includes(op) ? op : 'equals';
            input.type = typed ? types[field.value] : 'text';
            if (input.type === 'number') input.step = 'any';
            input.value = value;
            showValue();
        }
        update(initial.operator, initial.value);
        field.addEventListener('change', () => update('equals', ''));
        operator.addEventListener('change', showValue);
        const remove = button('Remove');
        remove.setAttribute('aria-label', `${title}: Remove lookup condition`);
        const entry = {value: () => ({field: field.value, operator: operator.value, value: input.disabled ? '' : input.value})};
        remove.addEventListener('click', () => {
            entries.splice(entries.indexOf(entry), 1);
            row.remove();
            add.disabled = false;
            changed();
        });
        row.append(field, operator, container, remove);
        list.append(row);
        entries.push(entry);
    }
    const add = button('Add condition');
    add.addEventListener('click', () => { addCondition(); add.disabled = entries.length >= 8; changed(); });
    panel.append(add);
    for (const condition of initial.conditions) addCondition(condition);
    add.disabled = entries.length >= 8;
    const selection = select([['unique', 'Unique match'], ['min', 'Minimum (Min)'], ['max', 'Maximum (Max)']], initial.selection.rule, `${title}: Lookup selection rule`);
    const basis = select(selectionFields.map(key => [key, labels[key]]), initial.selection.field, `${title}: Lookup selection field`);
    const basisLabel = labelled('Based on', basis);
    const selectionRow = node('div');
    selectionRow.className = 'crm-view-sorting';
    selectionRow.append(labelled('Select one record', selection), basisLabel);
    panel.append(selectionRow);
    function showBasis() { basisLabel.hidden = selection.value === 'unique'; }
    selection.addEventListener('change', showBasis);
    showBasis();
    const hint = node('p', 'Unique match requires exactly one matching record. Min/Max select a record; ties remain unresolved. ' + definition.hint);
    hint.className = 'subtle';
    panel.append(hint);
    const outputs = node('fieldset');
    outputs.className = 'analysis-edit-fields';
    outputs.append(node('legend', 'Columns to display'));
    const choices = new Map();
    for (const [key, label] of Object.entries(labels)) {
        const check = node('input');
        check.type = 'checkbox';
        check.checked = initial.outputs.includes(key);
        const wrap = labelled(label, check);
        wrap.className = 'resolve-confirm';
        outputs.append(wrap);
        choices.set(key, check);
        check.addEventListener('change', changed);
    }
    panel.append(outputs);
    const outputNote = node('p', 'Selected fields appear directly in the table. Fixed MAH columns are configured under Columns.');
    outputNote.className = 'subtle';
    panel.append(outputNote);
    return {
        panel,
        getValue() {
            return {match: join.value, conditions: entries.map(entry => entry.value()),
                selection: {rule: selection.value, field: basis.value},
                outputs: [...choices].filter(([, check]) => check.checked).map(([key]) => key)};
        },
    };
}
export function initialiseLookup(form, config, onOutputs) {
    const panel = node('details');
    panel.className = 'crm-filter-settings crm-view-lookups';
    panel.append(node('summary', 'Lookups'));
    const editors = new Map();
    function changed() {
        onOutputs([...editors.values()].flatMap(editor => editor.getValue().outputs));
        form.dispatchEvent(new CustomEvent('crm-view-change'));
    }
    const relation = select(definitions.map(item => [item.key, item.title]), 'declaration_lookup', 'Lookup relation');
    panel.append(labelled('Relation', relation));
    for (const definition of definitions) {
        let initial = config[definition.key];
        if (definition.key === 'declaration_lookup' && (!initial || Object.hasOwn(initial, 'rule'))) {
            const legacy = initial || {rule: 'latest', year: null};
            initial = {match: 'and', conditions: legacy.rule === 'year' ? [{field: 'sd_year', operator: 'equals', value: String(legacy.year)}] : [],
                selection: {rule: legacy.rule === 'year' ? 'unique' : 'max', field: 'sd_year'},
                outputs: [...new Set([...(config.columns || []).filter(key => key.startsWith('sd_')),
                    ...config.conditions.map(c => c.field).filter(key => key.startsWith('sd_')),
                    ...(config.sort?.startsWith('sd_') ? [config.sort] : [])])]};
        }
        initial ||= {match: 'and', conditions: [], selection: {rule: 'unique', field: definition.selectionFields[0]}, outputs: []};
        const editor = relationEditor(form, definition, initial, changed);
        editors.set(definition.key, editor);
        panel.append(editor.panel);
    }
    function showRelation() {
        for (const [key, editor] of editors) editor.panel.hidden = key !== relation.value;
    }
    const resumeKey = 'crm-lookup-relation';
    try {
        const saved = sessionStorage.getItem(resumeKey);
        if (editors.has(saved)) relation.value = saved;
    } catch {}
    relation.addEventListener('change', event => {
        event.stopPropagation();
        showRelation();
        try { sessionStorage.setItem(resumeKey, relation.value); } catch {}
    });
    showRelation();
    changed();
    return {panel, getValue() {return Object.fromEntries([...editors].map(([key, editor]) => [key, editor.getValue()]));}};
}
