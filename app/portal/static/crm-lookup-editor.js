// Structured relation selection. No expressions or executable code are accepted.
const labels = {sd_year: 'SD year', sd_packs: 'RX packs sold', sd_sales_group: 'RX sales group', sd_status: 'Declaration status', sd_declaration: 'Declaration', sd_selection: 'Selection result'};
const numeric = new Set(['sd_year', 'sd_packs']);
const filterKeys = ['sd_year', 'sd_packs', 'sd_sales_group', 'sd_status'];
const ops = {equals: 'is', not_equals: 'is not', greater_than: '>', greater_equal: '≥', less_than: '<', less_equal: '≤', contains: 'contains', empty: 'is empty', not_empty: 'is not empty'};
function node(tag, text = '') { const n = document.createElement(tag); n.textContent = text; return n; }
function select(items, value, label) {const n=node('select'); for(const [key,text] of items)n.append(new Option(text,key)); n.value=value; n.setAttribute('aria-label',label); return n;}
function labelled(text, control) {const n=node('label',text);n.append(control);return n;}
function button(text) {const n=node('button',text);n.type='button';n.className='portal-button portal-button-secondary';return n;}
export function initialiseLookup(form, config, onOutputs) {
    const existing = config.declaration_lookup || {rule:'latest',year:null};
    const legacy = Object.hasOwn(existing,'rule');
    const initial = legacy ? {
        match:'and', conditions:existing.rule==='year'?[{field:'sd_year',operator:'equals',value:String(existing.year)}]:[],
        selection:{rule:existing.rule==='year'?'unique':'max',field:'sd_year'},
        outputs:[...new Set(['sd_year','sd_selection',...(config.columns||[]).filter(k=>k.startsWith('sd_')), ...config.conditions.map(c=>c.field).filter(k=>k.startsWith('sd_')), ...(config.sort?.startsWith('sd_')?[config.sort]:[])])],
    } : existing;
    const panel=node('details');panel.className='crm-filter-settings crm-view-lookups';panel.append(node('summary','Lookups'));
    panel.append(node('h3','Self-declarations'));
    const note=node('p','Conditions filter the related declarations of each MAH. All outputs come from one selected record.');note.className='subtle';panel.append(note);
    const join=select([['and','All conditions (AND)'],['or','Any condition (OR)']],initial.match,'Match lookup conditions');
    panel.append(labelled('Match',join));
    const list=node('div');list.className='crm-condition-list';panel.append(list);
    const entries=[];
    function addCondition(initial={field:'sd_year',operator:'equals',value:''}) {
        if(entries.length>=8)return;
        const row=node('div');row.className='crm-condition-row';
        const field=select(filterKeys.map(k=>[k,labels[k]]),initial.field,'Lookup condition field');
        const operator=select([],null,'Lookup condition operator');
        const container=node('div');container.className='crm-condition-value';const input=node('input');container.append(input);input.setAttribute('aria-label','Lookup condition value');input.maxLength=200;
        function showValue(){container.hidden=['empty','not_empty'].includes(operator.value);input.disabled=container.hidden;input.required=!container.hidden;}
        function update(op,value){const keys=numeric.has(field.value)?['equals','not_equals','greater_than','greater_equal','less_than','less_equal','empty','not_empty']:['equals','not_equals','contains','empty','not_empty'];operator.replaceChildren(...keys.map(k=>new Option(ops[k],k)));operator.value=keys.includes(op)?op:'equals';input.type=numeric.has(field.value)?'number':'text';input.step='any';input.value=value;showValue();}
        update(initial.operator,initial.value);field.addEventListener('change',()=>update('equals',''));operator.addEventListener('change',showValue);
        const remove=button('Remove');remove.setAttribute('aria-label','Remove lookup condition');
        const entry={value:()=>({field:field.value,operator:operator.value,value:input.disabled?'':input.value})};
        remove.addEventListener('click',()=>{entries.splice(entries.indexOf(entry),1);row.remove();add.disabled=false;form.dispatchEvent(new CustomEvent('crm-view-change'));});
        row.append(field,operator,container,remove);list.append(row);entries.push(entry);
    }
    const add=button('Add condition');add.addEventListener('click',()=>{addCondition();add.disabled=entries.length>=8;form.dispatchEvent(new CustomEvent('crm-view-change'));});panel.append(add);
    for(const c of initial.conditions)addCondition(c);add.disabled=entries.length>=8;
    const selection=select([['unique','Unique match'],['min','Minimum (Min)'],['max','Maximum (Max)']],initial.selection.rule,'Lookup selection rule');
    const basis=select([['sd_year','SD year'],['sd_packs','RX packs sold']],initial.selection.field,'Lookup selection field');
    const basisLabel=labelled('Based on',basis);const selectionRow=node('div');selectionRow.className='crm-view-sorting';selectionRow.append(labelled('Select one record',selection),basisLabel);panel.append(selectionRow);
    const showBasis=()=>{basisLabel.hidden=selection.value==='unique';};selection.addEventListener('change',showBasis);showBasis();
    const hint=node('p','Unique match requires exactly one matching record. Min/Max select a record; ties remain unresolved. Duplicate MAH/year records are data errors.');hint.className='subtle';panel.append(hint);
    const outputs=node('fieldset');outputs.className='analysis-edit-fields';outputs.append(node('legend','Output fields'));
    const choices=new Map();for(const [key,label] of Object.entries(labels)){const check=node('input');check.type='checkbox';check.checked=initial.outputs.includes(key);check.disabled=['sd_year','sd_selection'].includes(key);const wrap=labelled(label+(check.disabled?' · required':''),check);wrap.className='resolve-confirm';outputs.append(wrap);choices.set(key,check);check.addEventListener('change',refresh);}
    panel.append(outputs);
    function refresh(){onOutputs([...choices].filter(([,c])=>c.checked).map(([k])=>k));form.dispatchEvent(new CustomEvent('crm-view-change'));}
    refresh();
    return {panel,getValue(){return {match:join.value,conditions:entries.map(e=>e.value()),selection:{rule:selection.value,field:basis.value},outputs:[...choices].filter(([,c])=>c.checked).map(([k])=>k)};}};
}
