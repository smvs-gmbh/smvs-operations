// One canonical quick-filter value keeps saved views, links and exports aligned.
export function controlValue(control) {
    if (control.type === 'checkbox') return control.checked ? control.value : '';
    if (control.multiple) return [...control.selectedOptions].map(option => option.value).join(',');
    return control.value;
}
export function restoreControl(control, value) {
    if (control.type === 'checkbox') control.checked = ['true','yes','on','1'].includes(value);
    else if (control.multiple) {
        const selected = new Set(String(value || '').split(',').filter(Boolean));
        for (const code of selected) if (![...control.options].some(option => option.value === code)) control.add(new Option(code, code));
        for (const option of control.options) option.selected = selected.has(option.value);
        control.dispatchEvent(new Event('portal-select-sync'));
    } else control.value = value;
}
export function enhanceMultipleSelects(form) {
    for (const select of form.querySelectorAll('select[data-multiple-select]')) {
        if (select.dataset.enhanced) continue;
        const label = select.closest('label');
        if (!label) continue;
        select.dataset.enhanced = 'true';
        const group = document.createElement('div');group.className = 'multiple-select';
        const title = document.createElement('span');title.textContent = label.firstChild.textContent.trim();
        const trigger = document.createElement('button');trigger.type = 'button';trigger.className = 'portal-button portal-button-secondary multiple-select-trigger';
        trigger.setAttribute('aria-label', title.textContent);trigger.setAttribute('aria-expanded', 'false');
        const choices = document.createElement('fieldset');choices.hidden = true;choices.className = 'multiple-select-choices';
        choices.id = 'multiple-select-' + select.name;trigger.setAttribute('aria-controls', choices.id);
        const legend = document.createElement('legend');legend.textContent = title.textContent;choices.append(legend);
        const commands = document.createElement('div');commands.className = 'multiple-select-commands';
        const selectAll = document.createElement('button');selectAll.type = 'button';selectAll.textContent = 'Select all';
        const clear = document.createElement('button');clear.type = 'button';clear.textContent = 'Clear selection';
        commands.append(selectAll, clear);choices.append(commands);
        const checks = [];
        const sync = () => {
            const options = [...select.selectedOptions];
            const summary = options.length ? options.map(option => option.textContent).join(', ') : 'All markets';
            trigger.textContent = options.length > 4 ? `${options.length} markets selected` : summary;
            trigger.title = summary;trigger.setAttribute('aria-label', title.textContent + ': ' + trigger.textContent);
            for (const [check, option] of checks) check.checked = option.selected;
        };
        for (const option of select.options) {
            const entry = document.createElement('label');const check = document.createElement('input');check.type = 'checkbox';check.value = option.value;
            check.addEventListener('change', () => {option.selected = check.checked;select.dispatchEvent(new Event('change', {bubbles:true}));});
            checks.push([check, option]);entry.append(check, document.createTextNode(option.textContent));choices.append(entry);
        }
        for (const [button, selected] of [[selectAll,true],[clear,false]]) button.addEventListener('click', () => {
            for (const option of select.options) option.selected = selected;
            select.dispatchEvent(new Event('change', {bubbles:true}));
        });
        trigger.addEventListener('click', () => {choices.hidden = !choices.hidden;trigger.setAttribute('aria-expanded', String(!choices.hidden));if (!choices.hidden) checks[0]?.[0].focus();});
        group.addEventListener('keydown', event => {if (event.key === 'Escape' && !choices.hidden) {event.preventDefault();event.stopPropagation();choices.hidden=true;trigger.setAttribute('aria-expanded','false');trigger.focus();}});
        const help = label.querySelector('small');
        label.replaceWith(group);select.hidden = true;group.append(title, select, trigger, choices);if (help) group.append(help);
        select.addEventListener('change', sync);select.addEventListener('portal-select-sync', sync);sync();
    }
}
