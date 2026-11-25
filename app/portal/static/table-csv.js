import {installActions} from './table-actions.js?v=csv-1';

const installed = new WeakMap();
const encoder = new TextEncoder();
const MAX_PAYLOAD = 50 * 1024 * 1024;

export function headerFields(table) {
    const row = table.tHead?.rows[0] || [...table.rows].find(r => [...r.cells].some(c => c.tagName === 'TH'));
    let index = 0;
    return row ? [...row.cells].map(cell => {
        const selection = cell.dataset.column === 'selection' || (!cell.dataset.column && !!cell.querySelector('input[type="checkbox"]'));
        const key = cell.dataset.column || (selection ? 'selection' : 'c' + index);
        if (!selection) index++;
        return {key, label: cell.textContent.trim().replace(/\s+/g, ' '), cell};
    }) : [];
}

export function cellText(cell) {
    const copy = cell.cloneNode(true);
    // Export data, not selection controls, operational actions or navigation arrows.
    for (const control of copy.querySelectorAll('form,button,input,select,textarea,.row-arrow,.source-row-link,[hidden],[data-csv-exclude]')) control.remove();
    for (const block of [...copy.querySelectorAll('small,div,p,li,pre,br')].reverse()) {
        block.before('\n');
        if (block.tagName !== 'BR') block.after('\n');
    }
    return copy.textContent.split(/\r?\n/).map(line => line.trim()).filter(Boolean).join('\n').trim();
}

function tableRecords(table, visibleOnly = false) {
    const fields = headerFields(table);
    return [...table.tBodies].flatMap(body => [...body.rows])
        .filter(row => !row.querySelector('th') && (!visibleOnly || !row.hidden))
        .filter(row => row.cells.length === fields.length && [...row.cells].every(cell => cell.colSpan === 1))
        .map(row => Object.fromEntries(fields.map((field, index) => [field.key, cellText(row.cells[index])])));
}

function paginationFor(table) {
    const next = (table.closest('.table-scroll') || table).nextElementSibling;
    return next?.classList.contains('pagination') ? next : null;
}

function pageInfo(table) {
    const pager = paginationFor(table);
    if (!pager) return null;
    const info = Object.fromEntries(['page','pages','total','first','last'].map(key => [key, Number(pager.dataset[key])]));
    if (Object.values(info).some(n => !Number.isSafeInteger(n) || n < 0) || info.pages < 1) {
        throw new Error('Reload this view before downloading CSV.');
    }
    return info;
}

function numberValue(value) {
    return value && value !== '—' ? Number(value.replace(/[’,\s']/g, '')) : NaN;
}

export function applyReportView(records, config, schema, query = '') {
    const kinds = new Map(schema.map(field => [field.key, field.type]));
    const matched = records.filter(record => (config.conditions || []).every(condition => {
        const value = (record[condition.field] || '').toLocaleLowerCase();
        const expected = String(condition.value).toLocaleLowerCase();
        if (condition.operator === 'empty') return !value || value === '—';
        if (condition.operator === 'not_empty') return !!value && value !== '—';
        if (condition.operator === 'contains') return value.includes(expected);
        const kind = kinds.get(condition.field);
        if (kind === 'date') return condition.operator === 'before' ? value < expected : condition.operator === 'after' ? value > expected : value === expected;
        if (kind !== 'number') return value === expected;
        const numeric = numberValue(value), target = Number(expected);
        return condition.operator === 'equals' ? numeric === target : condition.operator === 'less_than' ? numeric < target : numeric > target;
    })).filter(record => !query || Object.values(record).join(' ').toLocaleLowerCase().includes(query.toLocaleLowerCase()));
    if (config.sort) {
        const direction = config.direction === 'desc' ? -1 : 1;
        matched.sort((a,b) => {
            const left = a[config.sort] || '', right = b[config.sort] || '';
            if (kinds.get(config.sort) !== 'number') return left.localeCompare(right,undefined,{numeric:true}) * direction;
            const first = numberValue(left), second = numberValue(right);
            if (Number.isNaN(first)) return Number.isNaN(second) ? 0 : 1;
            if (Number.isNaN(second)) return -1;
            return (first - second) * direction;
        });
    }
    return matched;
}

function freezeScope(url, state, form) {
    if (!state?.config || !form) return url;
    const prefix = form.dataset.viewPrefix || '';
    url.searchParams.set(prefix + 'view', 'all');
    url.searchParams.delete(prefix + 'preset');
    url.searchParams.set(prefix + 'rules', JSON.stringify(state.config.conditions || []));
    url.searchParams.set(prefix + 'sort', state.config.sort || '');
    url.searchParams.set(prefix + 'direction', state.config.direction || 'asc');
    for (const [name, value] of Object.entries(state.config.quick_filters || {})) {
        const key = form.dataset.localSearch && name === 'q' ? prefix + 'q' : name;
        url.searchParams.set(key, value);
    }
    return url;
}

function stamp(doc) {
    return [...doc.querySelectorAll('.source-strip,.crm-list-status')].map(node => node.textContent.trim()).join('|');
}

async function collectRows(table, context, state, signal, progress, label = 'CSV') {
    const info = pageInfo(table);
    if (!info || info.pages === 1) return tableRecords(table, true);
    const current = new URL(location.href);
    const source = freezeScope(new URL(current), state, context.form);
    const index = [...document.querySelectorAll('main table')].indexOf(table);
    const expectedHeaders = headerFields(table).filter(f => f.key !== 'selection').map(f => [f.key, f.label]);
    const sourceStamp = stamp(document);
    let records = [], expectedPages;
    for (let page = 1; ; page++) {
        if (signal.aborted) throw new DOMException('Cancelled', 'AbortError');
        let selected = table;
        {
            const url = new URL(source); url.searchParams.set('page', page);
            const response = await fetch(url, {credentials:'same-origin',cache:'no-store',headers:{'X-Portal-CSV':'1'},signal});
            if (!response.ok || new URL(response.url).origin !== current.origin || new URL(response.url).pathname !== current.pathname) {
                throw new Error('A page of this view could not be loaded. Sign in or reload the view and try again.');
            }
            const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
            selected = doc.querySelectorAll('main table')[index];
            if (!selected || stamp(doc) !== sourceStamp) throw new Error('The source changed during export. Reload the view and try again.');
            const actualHeaders = headerFields(selected).filter(f => f.key !== 'selection').map(f => [f.key,f.label]);
            const canonical = fields => JSON.stringify([...fields].sort((a,b)=>a[0].localeCompare(b[0])));
            if (canonical(actualHeaders) !== canonical(expectedHeaders)) throw new Error('The table changed during export. Reload the view and try again.');
        }
        const meta = pageInfo(selected);
        if (page === 1) expectedPages = meta?.pages;
        if (!meta || meta.page !== page || meta.pages !== expectedPages || meta.pages > 10000 || meta.total !== info.total) {
            throw new Error('The result set changed during export. Reload the view and try again.');
        }
        const rows = tableRecords(selected);
        if (rows.length !== meta.last - meta.first + 1 || meta.first !== records.length + 1) {
            throw new Error('The complete view could not be retrieved. Reload the view and try again.');
        }
        records.push(...rows);
        progress(`Preparing ${label}… ${records.length.toLocaleString()} of ${info.total.toLocaleString()} rows`);
        if (records.length > 400000) throw new Error('This view is too large for one file. Narrow the view and try again.');
        if (page === expectedPages) break;
    }
    if (records.length !== info.total) throw new Error('The complete view could not be retrieved. Reload the view and try again.');
    return state?.server ? records : applyReportView(records, state?.config || {}, state?.schema || [], state?.config?.quick_filters?.q || '');
}

export function installCsvDownload(table, context) {
    if (installed.has(table)) return;
    installed.set(table, context);
    const {workspace, form} = context;
    const actions = installActions(workspace, form);
    const area = document.createElement('div'); area.className = 'table-csv-controls';
    const download = document.createElement('button'); download.type='button'; download.className='portal-button'; download.textContent='Download CSV';
    const excel = document.createElement('button');excel.type='button';excel.className='portal-button';excel.textContent='Download Excel';
    const cancel = document.createElement('button'); cancel.type='button'; cancel.className='portal-button portal-button-secondary'; cancel.textContent='Cancel download';cancel.hidden=true;
    const status = document.createElement('p'); status.className='subtle'; status.setAttribute('role','status');status.setAttribute('aria-live','polite');
    const hint=document.createElement('p');hint.className='subtle';hint.style.flexBasis='100%';hint.textContent='Excel preserves leading zeros in identifiers.';
    area.append(excel,download,cancel,hint,status);actions.body.prepend(area);
    let state = context.standalone ? {server:false,config:null,schema:[]} : null;
    download.disabled = excel.disabled = !state;
    if (!state) status.textContent = 'Loading view…';
    form.addEventListener('portal-view-config', event => {
        state=structuredClone({...event.detail,server:event.detail.server ?? !form.dataset.viewPrefix});
        download.disabled=excel.disabled=false;status.textContent='';
    });
    let controller;
    cancel.addEventListener('click',()=>controller?.abort());
    async function generate(fileFormat){
        const label=fileFormat==='xlsx'?'Excel':'CSV';
        download.disabled=excel.disabled=true;cancel.hidden=false;controller=new AbortController();
        const progress=text=>status.textContent=text;
        try {
            const frozen=structuredClone(state);
            const types=new Map((frozen?.schema||[]).map(field=>[field.key,field.type]));
            const columns=headerFields(table).filter(f=>!f.cell.hidden&&f.key!=='selection'&&f.label&&f.label!=='Links / actions')
                .map(({key,label,cell})=>({key,label,type:(types.get(key)||(cell.classList.contains('numeric')?'number':'text'))==='number'?'number':'text'}));
            if (!columns.length) throw new Error('Select at least one data column before downloading CSV.');
            progress(`Preparing ${label}…`);
            const records=await collectRows(table,context,frozen,controller.signal,progress,label);
            if (controller.signal.aborted) throw new DOMException('Cancelled','AbortError');
            const fingerprint=JSON.stringify({url:location.pathname+location.search,config:frozen?.config,columns});
            const digest=await crypto.subtle.digest('SHA-256',encoder.encode(fingerprint));
            const view_hash=[...new Uint8Array(digest)].map(byte=>byte.toString(16).padStart(2,'0')).join('');
            const payload=JSON.stringify({source_path:location.pathname,table_key:table.dataset.crmColumns||context.key||'table',view_hash,columns,rows:records.map(record=>columns.map(c=>record[c.key]??''))});
            if (encoder.encode(payload).length>MAX_PAYLOAD) throw new Error('This view is too large for one file. Narrow the view and try again.');
            progress(`Generating ${label}… ${records.length.toLocaleString()} rows`);
            const response=await fetch('/table-exports/'+fileFormat,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:payload,signal:controller.signal});
            const mime=fileFormat==='xlsx'?'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':'text/csv';
            if (!response.ok || !response.headers.get('Content-Type')?.startsWith(mime) || !response.headers.get('X-Export-Receipt')) {
                const error=await response.json().catch(()=>null);
                throw new Error(typeof error?.detail==='string'?error.detail:`The ${label} file could not be generated. No file has been downloaded.`);
            }
            const blob=await response.blob();
            if (controller.signal.aborted) throw new DOMException('Cancelled','AbortError');
            const url=URL.createObjectURL(blob),link=document.createElement('a');
            link.href=url;link.download=response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1]||'view.'+fileFormat;
            document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
            progress(`${label} ready · ${records.length.toLocaleString()} rows`);
        } catch(error) {
            progress(error.name==='AbortError'?`${label} download cancelled.`:error.message||`The ${label} file could not be generated. Try again.`);
        } finally {download.disabled=excel.disabled=false;cancel.hidden=true;}
    }
    download.addEventListener('click',()=>generate('csv'));
    excel.addEventListener('click',()=>generate('xlsx'));
}

function installOtherTables() {
    let index=0;
    for (const table of document.querySelectorAll('main table')) {
        index++;
        if (table.dataset.crmColumns||installed.has(table)||table.closest('form,dialog')||!headerFields(table).length) continue;
        const workspace=table.closest('section,article,.panel')||table.parentElement;
        const toolbar=document.createElement('div');toolbar.className='review-body';toolbar.dataset.crmFilters='csv-table-'+index;
        const bar=document.createElement('div');bar.className='crm-view-bar';toolbar.append(bar);
        (table.closest('.table-scroll')||table).before(toolbar);
        installCsvDownload(table,{workspace,form:toolbar,standalone:true,key:'table-'+index});
    }
}
if (typeof document!=='undefined') {
    if(document.readyState==='complete')installOtherTables();
    else document.addEventListener('DOMContentLoaded',installOtherTables,{once:true});
}
