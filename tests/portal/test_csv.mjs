import test from 'node:test';
import assert from 'node:assert/strict';
import {applyReportView} from '../../app/portal/static/table-csv.js';

const schema=[{key:'code',type:'text'},{key:'packs',type:'number'},{key:'date',type:'date'}];
const records=[
    {code:'00042',packs:'0',date:'2026-11-01'},
    {code:'00043',packs:'1’200',date:'2026-11-02'},
    {code:'00044',packs:'100',date:'2026-11-03'},
    {code:'00045',packs:'—',date:'2026-11-04'},
    {code:'00046',packs:'',date:''},
];

test('report export and visible table share numeric rules and global ordering',()=>{
    const result=applyReportView(records,{conditions:[{field:'packs',operator:'greater_than',value:'0'}],sort:'packs',direction:'desc'},schema);
    assert.deepEqual(result.map(row=>row.code),['00043','00044']);
    assert.equal(result[0].packs,'1’200');
    assert.deepEqual(records.map(row=>row.code),['00042','00043','00044','00045','00046']);
});

test('unknown values are not zero; multiple conditions and search keep scope',()=>{
    assert.deepEqual(applyReportView(records,{conditions:[{field:'packs',operator:'equals',value:'0'}]},schema).map(r=>r.code),['00042']);
    const config={conditions:[{field:'packs',operator:'not_empty'},{field:'code',operator:'contains',value:'0004'}]};
    assert.deepEqual(applyReportView(records,config,schema,'00043').map(r=>r.code),['00043']);
    assert.deepEqual(applyReportView(records,{conditions:[{field:'packs',operator:'empty'}]},schema).map(r=>r.code),['00045','00046']);
});

test('numeric sort puts missing values last and date conditions stay typed',()=>{
    assert.deepEqual(applyReportView(records,{sort:'packs',direction:'desc'},schema).map(r=>r.code),['00043','00044','00042','00045','00046']);
    assert.deepEqual(applyReportView(records,{conditions:[{field:'date',operator:'before',value:'2026-11-03'},{field:'date',operator:'not_empty'}]},schema).map(r=>r.code),['00042','00043']);
});
