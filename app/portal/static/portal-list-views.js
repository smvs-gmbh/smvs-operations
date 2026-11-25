import {initialiseViews} from './crm-list-views.js?v=lookup-visibility-2';
import {installActions} from './table-actions.js?v=csv-1';
import {installCsvDownload,applyReportView,cellText} from './table-csv.js?v=crm-lookups-1';

function hash(value) { let h=2166136261; for(const c of value) h=Math.imul(h^c.charCodeAt(0),16777619); return (h>>>0).toString(36); }
function node(tag,cls,text) {const e=document.createElement(tag);e.className=cls||'';if(text)e.textContent=text;return e;}
function button(text) {const e=node('button','portal-button portal-button-secondary',text);e.type='button';return e;}
const primary = ['products','batches','organisations','locations','exceptions'];
const path=location.pathname;
const used=new Map();
for(const [index,table] of [...document.querySelectorAll('main .table-scroll > table')].entries()) {
    if(table.dataset.crmColumns || !table.tHead || table.closest('dialog, form')) continue;
    const section=table.closest('section,article') || table.parentElement.parentElement;
    const headers=[...table.tHead.rows[0].cells];
    if(!headers.length)continue;
    const root=path.slice(1);
    let identity=primary.includes(root)&&index===0?root:'t-'+hash(path.replace(/\/\d+(?=\/|$)/g,'/record')+'|'+(section.querySelector('h2')?.textContent.trim()||'')+'|'+headers.map(h=>h.textContent.trim()).join('|'));
    if(/^\/products\/\d+$/.test(path)&&/^Batch/i.test(headers[0].textContent.trim()))identity='product-batches';
    if(/^\/organisations\/\d+$/.test(path)&&/^Location/i.test(headers[0].textContent.trim()))identity='organisation-locations';
    if(path==='/workflows/registrations')identity='registrations';
    const occurrence=used.get(identity)||0;used.set(identity,occurrence+1);if(occurrence)identity='t-'+hash(identity+':'+occurrence);
    const schema=[];let col=0;
    for(const h of headers){
        const selection=h.querySelector('input[type="checkbox"]');
        const key=selection?'selection':'c'+col++;
        h.dataset.column=key;
        schema.push({key,label:h.textContent.trim()||'Links / actions',type:h.classList.contains('numeric')?'number':'text',column_only:!!table.querySelector('tbody tr')?.cells[h.cellIndex]?.querySelector('form')});
    }
    table.dataset.crmColumns=identity;
    table.dataset.pinnedColumns='c0'+(schema.some(f=>f.key==='selection')?',selection':'');
    const rows=[...table.tBodies].flatMap(body=>[...body.rows]).filter(r=>r.cells.length===headers.length);
    const original=rows.map(row=>({row,cells:[...row.cells]}));
    const wrapper=node('section','portal-table-panel');
    const scroll=table.parentElement;
    const pagination=scroll.nextElementSibling?.classList.contains('pagination')?scroll.nextElementSibling:null;
    const filter=[...section.querySelectorAll('form')].find(f=>f.method==='get'&&!f.closest('dialog')&&!f.dataset.crmFilters);
    const actions=section.querySelector('details.exception-actions');
    scroll.before(wrapper);
    const form=node('form','review-body review-form list-filters');form.method='get';form.setAttribute('role','search');
    form.dataset.crmFilters=identity;form.dataset.viewPrefix='tv_'+identity+'_';form.dataset.viewPath=path;
    const endpoint='/table-views/'+identity+'?schema='+encodeURIComponent(JSON.stringify(schema));
    form.dataset.viewEndpoint=endpoint;form.dataset.catalogueEndpoint=endpoint;
    const quick=node('div','review-controls');
    const scopes=node('details','crm-filter-settings');scopes.dataset.crmViewFilters='';
    const scopeControls=node('div','crm-view-sorting');scopes.append(node('summary','','Report scope'),scopeControls);
    if(filter){
        for(const control of [...filter.querySelectorAll('input[name],select[name]')]) {
            if(control.type==='hidden') {form.append(control);continue;}
            let label=control.closest('label');
            if(!label||label===filter) {label=node('label');label.append(document.createTextNode(control.getAttribute('aria-label')||control.name),control);}
            if(control.name==='q') {
                if(label.classList.contains('search-box')) {
                    label.classList.remove('search-box');
                    label.querySelector('[aria-hidden]')?.remove();
                    label.prepend(document.createTextNode('Search'));
                }
                quick.append(label);control.placeholder='Search …';
            }
            else scopeControls.append(label);
        }
        filter.remove();
    }
    if(!quick.children.length) {
        form.dataset.localSearch='true';
        const input=node('input');input.name='q';input.value=new URLSearchParams(location.search).get('tv_'+identity+'_q')||'';
        const label=node('label','','Search this table');label.append(input);quick.append(label);
    }
    const search=button('Search');search.type='submit';quick.append(search);
    form.append(quick,scopes);wrapper.append(form,scroll);if(pagination)wrapper.append(pagination);
    const result=node('p','portal-view-results subtle');wrapper.append(result);
    form.addEventListener('portal-view-config',event=>{
        if(event.detail.server)return;
        const config=event.detail.config;
        const entries=new Map(original.map(entry=>[
            Object.fromEntries(schema.map((field,index)=>[field.key,cellText(entry.cells[index])])),entry,
        ]));
        const matched=applyReportView([...entries.keys()],config,event.detail.schema,form.querySelector('[name="q"]')?.value||'')
            .map(record=>entries.get(record));
        for(const entry of original)entry.row.hidden=!matched.includes(entry);
        for(const entry of matched) table.tBodies[0].append(entry.row);
        result.textContent=`${matched.length} of ${original.length} rows in this table’s current report scope`;
    });
    if(actions) installActions(wrapper,form,actions);
    // Row-level forms retain their individual targets and permissions.
    const rowActions=original.filter(e=>e.row.querySelector('form[method="post"]'));
    if(!actions&&rowActions.length){
        const rowChecks=[];
        const content=node('details');content.append(node('summary','','Actions'));
        const help=node('p','subtle','Select rows to show their available actions. Each action applies to its named record.');content.append(help);
        for(const entry of rowActions){
            const group=node('section','portal-row-action');group.hidden=true;
            group.append(node('h3','',entry.cells[0].textContent.trim()));
            for(const f of [...entry.row.querySelectorAll('form[method="post"]')])group.append(f);
            content.append(group);
            const cell=entry.cells.find(c=>!c.textContent.trim()&&!c.querySelector('input'))||entry.cells[entry.cells.length-1];
            const check=node('input');check.type='checkbox';check.setAttribute('aria-label','Select '+entry.cells[0].textContent.trim());
            check.addEventListener('change',()=>group.hidden=!check.checked);cell.append(check);rowChecks.push(check);
        }
        const all=node('input');all.type='checkbox';all.setAttribute('aria-label','Select all rows on this page');
        all.addEventListener('change',()=>{for(const check of rowChecks){check.checked=all.checked;check.dispatchEvent(new Event('change'));}});
        headers[headers.length-1].prepend(all);
        table.dataset.pinnedColumns+=','+headers[headers.length-1].dataset.column;
        installActions(wrapper,form,content);
    }
    installCsvDownload(table,{workspace:wrapper,form});
    initialiseViews(form);
}
