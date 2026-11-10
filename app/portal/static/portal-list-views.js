import {initialiseViews} from './crm-list-views.js?v=checkbox-filters-2';
import {rightToolbox} from './right-toolbox.js?v=record-actions-1';

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
        const cellValue=(entry,key)=>{
            const i=schema.findIndex(f=>f.key===key);return entry.cells[i]?.textContent.trim()||'';
        };
        const matched=original.filter(entry=>config.conditions.every(c=>{
            const value=cellValue(entry,c.field).toLocaleLowerCase();const expected=String(c.value).toLocaleLowerCase();
            if(c.operator==='empty')return !value||value==='—';if(c.operator==='not_empty')return !!value&&value!=='—';
            if(c.operator==='contains')return value.includes(expected);
            const field=event.detail.schema.find(f=>f.key===c.field);
            if(c.operator==='equals'&&field.type!=='number')return value===expected;
            const numeric=Number(value.replace(/[’,\s']/g,'')),n=Number(expected);
            return c.operator==='equals'?numeric===n:c.operator==='less_than'?numeric<n:numeric>n;
        })).filter(entry=>!form.querySelector('[name="q"]')?.value||entry.row.textContent.toLowerCase().includes(form.querySelector('[name="q"]').value.toLowerCase()));
        if(config.sort) matched.sort((a,b)=>cellValue(a,config.sort).localeCompare(cellValue(b,config.sort),undefined,{numeric:true})*(config.direction==='desc'?-1:1));
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
    initialiseViews(form);
}
function installActions(workspace,form,source){
    const opener=button('Actions');
    const aside=node('aside','crm-view-toolbox portal-actions-toolbox');aside.hidden=true;
    aside.id='actions-'+form.dataset.crmFilters;aside.setAttribute('aria-label','Table actions');opener.setAttribute('aria-controls',aside.id);opener.setAttribute('aria-expanded','false');
    const close=button('Close');close.setAttribute('aria-label','Close actions toolbox');
    const heading=node('div','crm-toolbox-heading');heading.append(node('h2','','Actions'),close);
    const body=node('div','crm-toolbox-body review-form');
    for(const child of [...source.childNodes])if(child.nodeName!=='SUMMARY')body.append(child);
    source.remove();aside.append(heading,body);
    const backdrop=button('');backdrop.className='crm-toolbox-backdrop';backdrop.tabIndex=-1;backdrop.hidden=true;backdrop.setAttribute('aria-label','Close actions toolbox');
    workspace.append(backdrop,aside);
    const controller=rightToolbox({toolbox:aside,opener,close,backdrop,workspace});
    // View settings and actions share one workspace but cannot be open together.
    opener.addEventListener('click',()=>{
        const view=workspace.querySelector('.crm-view-toolbox:not(.portal-actions-toolbox)');
        if(view&&!view.hidden)workspace.querySelector('[aria-controls="'+view.id+'"]')?.click();
    }, {capture:true});
    form.addEventListener('click', event=>{
        if(event.target.closest('[aria-controls^="view-toolbox-"]')&&!aside.hidden) controller.hide(false);
    }, {capture:true});
    new MutationObserver(()=>{
        const bar=form.querySelector('.crm-view-bar');if(bar&&!bar.contains(opener))bar.append(opener);
    }).observe(form,{childList:true,subtree:true});
}
