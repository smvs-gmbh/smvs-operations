'use strict';
const $=id=>document.getElementById(id);
const previewParams = new URLSearchParams(window.location.search);
const isMah = previewParams.get('view') === 'mah';
const yesNo = {yes: 'Yes', no: 'No'};
const packComparison = {...yesNo, not_checked: 'Not checked'};
const ownSideFindings = new Set(['on_my_side','process_error','technical_error','other_error']);
const findingChoices = {
 process_error: ['Process or handling error on my side'],
 technical_error: ['Scanner or software error on my side'],
 other_error: ['Other issue on my side'],
 on_my_side: ['Root cause on my side', 'Confirm your finding and report your CAPA status.'],
 not_my_side: ['Root cause not on my side', 'SMVS will review your finding.'],
 investigating: ['Still investigating', 'You can send an interim update while checks are open.']
};
const capaStatuses = {implemented: 'Implemented', planned: 'Planned', pending: 'Not yet planned'};
const scenarios={
 a7:{ref:'DEMO-A7-REPEAT · A7',title:'Resolved locally by SMVS',explanation:'The pack was already marked Exported at your location.',why:'How SMVS reached this decision',summary:'The same pack was exported and then submitted for Export again at the same reported location.',facts:['Successful Export followed by a rejected repeat three seconds later.','Exact source location identifiers match.','No conflicting state change in the retained report sequence.'],source:'Fictional Pack Audit Trail · repeated-Export analysis',decision:'Manual NMVO decision · Demo reviewer · 2026-11-10 09:20 UTC',code:'51320801',batch:'DEMO2601',serial:'12345678901234',process:'Export · same-location repeat'},
 a3:{ref:'DEMO-A3-BULK · A3',title:'Your findings are needed',explanation:'Compare the pack with the values shown.',why:'What we already know',summary:'The serial was not found during a bulk verification.',facts:['The records checked contain 28 other batches for this product.','The reported batch was absent from the records dated 2026-11-10. Its status at the time of the alert is unknown.','No exact-batch length reference or retained Pack Audit Trail is available.'],source:'NMVS alert and batch records · 2026-11-10 · fictional identifiers',decision:'No cause or responsibility has been assigned.',code:'41020001',batch:'DEMO2601',serial:'12345678901234',process:'Bulk verification · no IMT recorded'},
 pmd:{ref:'DEMO-A3-PMD · A3',title:'Your findings are needed',explanation:'Compare the pack with the values shown.',why:'What we already know',summary:'Product master data are present, but no batches are observed in the available reference. Upload status still needs clarification.',facts:['Owner-described Swiss scenario; simulated for this design.','No exact-batch serial reference is available.','No-batch observation does not prove that no historical upload occurred.'],source:'Simulated PMD-only scenario · operation code and processing route not established',decision:'SMVS would clarify pack-data upload with the MAH if needed.',code:'Not established',batch:'DEMO2602',serial:'98765432109876',process:'Not established in this example'},
 a2: {
  ref: 'DEMO-A2-DEFERRED · A2',
  explanation: 'The reported batch could not be found.',
  summary: 'SMVS has deferred review of this recurring alert pattern.',
  facts: ['Review due on 2026-11-18. The alert remains in the MAH monthly report.'],
  source: 'Fictional rule example',
  decision: 'Local deferral',
  code: 'Not established',
  batch: 'DEMO2603',
  serial: 'Not provided in this example',
  process: 'Not established in this example'
 },
 'a2-open': {
  ref: 'DEMO-A2-OPEN · A2',
  explanation: 'The system could not find the reported batch.',
  summary: 'The batch was absent from the records checked. Other batches for this product were found.',
  facts: ['The available upload history has no match for this batch.'],
  source: 'Fictional alert and batch records',
  decision: 'SMVS review pending',
  code: 'Not provided in this example',
  batch: 'DEMO2604',
  serial: '11000000002604',
  process: 'Verification',
  observation: 'Does the batch number shown match the printed batch?',
  mahChecks: ['Was this batch uploaded?', 'Was this batch distributed to the relevant market?']
 },
 'a7-open': {
  ref: 'DEMO-A7-DESTROY · A7',
  explanation: 'The system rejected the Destroy request because the pack was already marked Destroyed.',
  summary: 'The requested and reported states match.',
  facts: ['The alert does not identify the location or time of the previous state change.'],
  source: 'Fictional alert record',
  decision: 'SMVS review pending',
  code: 'Not provided in this example',
  batch: 'DEMO2605',
  serial: '11000000002605',
  process: 'Destroy',
  extraDetails: [['Requested state', 'Destroyed'], ['Reported state', 'Destroyed']],
  observation: 'Do your local records show an earlier successful Destroy request for this pack?'
 },
 a24: {
  ref: 'DEMO-A24-STATE · A24',
  explanation: 'The system rejected the dispensing request. The pack had already been marked as destroyed at another location. Set the pack aside for SMVS review.',
  summary: 'The reported state was Destroyed when Supply was requested.',
  facts: ['The audit trail shows the earlier change from Active to Destroyed. The source response reports a different location.'],
  source: 'Fictional alert and Pack Audit Trail',
  decision: 'SMVS review pending',
  code: '51220400',
  batch: 'DEMO2606',
  serial: '11000000002606',
  process: 'Supply Single Pack',
  extraDetails: [['Requested state', 'Supplied'], ['Reported state', 'Destroyed']],
  confirmSource: true
 },
 'a24-imt': {
  ref: 'DEMO-A24-IMT · A24',
  explanation: 'The system rejected the dispensing request. The pack was already marked as exported. Set the pack aside for SMVS review.',
  summary: 'The intermarket alert reports a dispensing request from Sweden and an earlier update in the EU market context.',
  facts: ['The two reported location identifiers differ.'],
  source: 'Fictional identifiers based on an observed intermarket pattern',
  decision: 'SMVS review pending',
  code: 'Unavailable in the source record',
  batch: 'DEMO2609',
  serial: '11000000002609',
  process: 'National System Intermarket',
  extraDetails: [['Requested state', 'Supplied'], ['Reported state', 'Exported']],
  confirmSource: true
 },
 a52: {
  ref: 'DEMO-A52-EXPIRY · A52',
  explanation: 'The expiry date sent by your system differs from the stored expiry date.',
  summary: 'The submitted expiry is 30 September 2028. The stored expiry is 31 October 2028.',
  facts: ['Compare the printed expiry with the submitted and stored dates. The discrepancy may involve the pack label or stored data.'],
  source: 'Fictional alert record',
  decision: 'SMVS review pending',
  code: 'Not provided in this example',
  batch: 'DEMO2607',
  serial: '11000000002607',
  process: 'Verification',
  expiry: '30 Sep 2028',
  extraDetails: [['Expiry stored', '31 Oct 2028']],
  observation: 'Does the submitted expiry match the date printed on the pack?'
 },
 a68: {
  ref: 'DEMO-A68-BATCH · A68',
  explanation: 'The batch number sent by your system differs from the stored batch number.',
  summary: 'The submitted batch is DEMO2608. The stored batch is DEMO260B.',
  facts: ['Compare the batch printed on the pack with the submitted value.'],
  source: 'Fictional alert record',
  decision: 'SMVS review pending',
  code: 'Not provided in this example',
  batch: 'DEMO2608',
  serial: '11000000002608',
  process: 'Verification',
  extraDetails: [['Batch stored', 'DEMO260B']],
  observation: 'Does the submitted batch number match the batch printed on the pack?'
 }
};
const endUserFindings = ['process_error','technical_error','other_error','not_my_side','investigating'];
const packChecks = {
 'a2-open': {label:'Submitted batch', field:'batch', followUp:'SMVS can check whether the batch was uploaded.'},
 a3: {label:'Submitted serial number', field:'serial', followUp:'SMVS can follow up on the pack upload.'},
 pmd: {label:'Submitted serial number', field:'serial', followUp:'SMVS can follow up on the pack upload.'},
 a52: {label:'Submitted expiry', field:'expiry', followUp:'SMVS can compare the printed and stored expiry dates.'},
 a68: {label:'Submitted batch', field:'batch', followUp:'SMVS can compare the printed and stored batch numbers.'}
};
let active='a3',data={},messages=[];
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function detail(label,value){const n=document.createElement('div');n.append(el('dt',label),el('dd',value));return n;}
function renderMessages(){const root=$('messages');root.replaceChildren();for(const text of messages){const item=el('li');item.append(el('strong','Your organisation · submitted to SMVS in this simulation'),el('p',text));root.append(item);}}
function setScenario(key){
 active=key;
 data={source:'',comparison:'',technical:'',photo:'',otherCause:false,comment:'',capa:'',finding:''};
 messages=[];
 const scenario=scenarios[key];
 const resolved=key==='a7';
 const deferred=key==='a2';
 const guided=!resolved&&!deferred;
 $('finding-change').hidden=true;
 renderAudit(key);
 $('case-ref').textContent=scenario.ref;
 $('title').textContent=alertTitles[key];
 $('case-status').textContent=caseStatuses[key]??'Open';
 $('explanation').textContent=caseExplanation(key);
 $('outcome-icon').textContent=resolved?'✓':'?';
 $('outcome-icon').classList.toggle('pending',!resolved);
 $('resolved-action').hidden=!resolved||isMah;
 $('guided-action').hidden=!guided||(isMah&&!mahChecks(key));
 $('deferred-action').hidden=!deferred;
 updateQuestions(key);
 $('analysis-line').textContent=analysisLines[key];
 $('compact-evidence').textContent=[scenario.summary,...scenario.facts].join(' ');
 $('compact-source').textContent=scenario.source+' · '+scenario.decision;
 const packDetails=[
  ['Alert',scenario.ref],['Operation code',scenario.code],['Process',scenario.process],
  ['Batch submitted',scenario.batch],['Serial submitted',scenario.serial],
  ...(scenario.expiry?[['Expiry submitted',scenario.expiry]]:[]),
  ...(scenario.extraDetails??[])
 ];
 $('pack-details').replaceChildren(...packDetails.map(([label,value])=>detail(label,value)));
 $('inline-evidence').open=false;
 $('details').open=window.matchMedia('(min-width: 850px)').matches;
 $('commitment-form').reset();
 $('resolved-capa').disabled=false;
 $('save-commitment').hidden=true;
 $('commitment-receipt').hidden=true;
 $('message-receipt').hidden=true;
 $('message-form').reset();
 $('conversation').close();
 $('review-state').hidden=true;
 $('guided-form').hidden=false;
 $('boundary-note').hidden=!resolved;
 renderMessages();
 renderStep();
}
const alertTitles = {
 a3: 'A3 · Serial number not found', pmd: 'A3 · Serial number not found',
 a2: 'A2 · Batch not found', 'a2-open': 'A2 · Batch not found',
 a7: 'A7 · Pack already in requested state', 'a7-open': 'A7 · Pack already in requested state',
 a24: 'A24 · Pack already decommissioned at another location',
 'a24-imt': 'A24 · Pack already marked as exported',
 a52: 'A52 · Expiry date discrepancy',
 a68: 'A68 · Batch number mismatch'
};
const caseStatuses = {a2: 'Deferred by rule', a7: 'Resolved locally by SMVS'};
const analysisLines = {
 a3: 'No match for this batch in the records checked.',
 pmd: 'Product known. No batches found in the records checked.',
 a2: 'Recurring pattern under SMVS review.',
 'a2-open': 'Other batches found for this product. No match for the reported batch.',
 a7: 'Repeat export at the same location, 3 seconds later.',
 'a7-open': 'Pack already Destroyed. Earlier operation details are unavailable.',
 a24: 'Previous status change at a different location.',
 'a24-imt': 'Different reported locations for the prior update and dispensing attempt.',
 a52: 'Submitted and stored expiry dates differ.',
 a68: 'Submitted and stored batch numbers differ.'
};
function mahChecks(key){
 if(key==='a3'||key==='pmd') return ['Was this batch uploaded?', 'Was this serial accepted in the upload?'];
 return scenarios[key].mahChecks;
}
function caseExplanation(key){
 if(isMah&&mahChecks(key)) return 'Check the upload for the reported batch.';
 if(isMah&&key==='a7') return 'SMVS reviewed a repeated Export request.';
 return scenarios[key].explanation;
}
function updateQuestions(key){
 const scenario=scenarios[key];
 const showSource=!isMah&&Boolean(scenario.confirmSource);
 $('source-check').hidden=!showSource;
 $('source-check').disabled=!showSource;
 $('other-cause').closest('.other-cause').hidden=!isMah;
 $('other-cause').disabled=!isMah;
 const reference=$('comparison-reference');
 const packCheck=isMah?null:packChecks[key];
 reference.hidden=!packCheck;
 reference.textContent=packCheck?packCheck.label+' · '+scenario[packCheck.field]:'';
 if(isMah){
  const [comparison,technical]=mahChecks(key)??[];
  renderCheck('comparison',comparison,yesNo);
  renderCheck('technical',technical,yesNo);
  return;
 }
 const question=scenario.observation??(packCheck?'Does the serial number shown match the one printed on the pack?':null);
 renderCheck('comparison',question,packCheck?packComparison:yesNo);
 renderCheck('technical',null,yesNo);
}
function renderGuidance(){
 const hint=$('next-check');
 const packshot=$('packshot-control');
 hint.hidden=isMah;
 packshot.hidden=true;
 if(isMah) return;
 const check=packChecks[active];
 if(!check){
  hint.textContent='Check your local dispensing records. SMVS can review the earlier status change.';
  if(active==='a7-open'){
   hint.textContent=data.comparison==='no'
    ? 'Check what triggered this Destroy request. SMVS can review the earlier status change.'
    : 'Check whether a local process or an automatic software retry triggered the repeat request.';
  }
  return;
 }
 if(data.comparison==='not_checked'){
  hint.textContent='If the pack becomes available, compare the printed value and update your findings.';
  return;
 }
 packshot.hidden=!data.comparison;
 const messages={
  yes:'Check for a local workflow or software issue. '+check.followUp,
  no:'Check manual entry and scanner settings. A packshot can help SMVS review the difference.'
 };
 hint.textContent=messages[data.comparison]??'Check the scanner, software and any manual entry used for this verification.';
}
function renderCheck(name,question,choices){
 const fieldset=$(name+'-check');
 fieldset.hidden=!question;
 fieldset.disabled=!question;
 $(name+'-question').textContent=question??'';
 renderRadioOptions(name,choices);
}
function renderRadioOptions(name,choices,required=false){
 const options=Object.entries(choices).map(([value,labelText])=>{
  const input=el('input');
  input.type='radio';
  input.name=name;
  input.value=value;
  input.required=required;
  const label=el('label');
  label.append(input,labelText);
  return label;
 });
 $(name+'-options').replaceChildren(...options);
}
function renderStep(){
 for(const name of ['source','comparison','technical','finding','guided-capa']){
  const value=name==='guided-capa'?data.capa:data[name];
  document.querySelectorAll(`input[name="${name}"]`).forEach(input=>input.checked=input.value===value);
 }
 $('other-cause').checked=data.otherCause;
 $('other-comment').value=data.comment;
 syncFinding();
 $('photo-file').value='';
 $('photo-label').textContent=data.photo?'Selected: '+data.photo+' · not uploaded':'Optional';
 $('guided-title').textContent='Your investigation';
}
function summary(){
 const answers=packComparison;
 const lines=[];
 if(!$('source-check').hidden){
  lines.push('Pack source confirmed: '+(answers[data.source]??'Not answered'));
 }
 for(const name of ['comparison','technical']){
  if($(name+'-check').hidden) continue;
  lines.push($(name+'-question').textContent+' · '+(answers[data[name]]??'Not answered'));
 }
 if(data.otherCause){
  lines.push($('other-cause-label').textContent);
 }
 if((data.otherCause||data.finding==='other_error')&&data.comment.trim()) lines.push('Comment: '+data.comment.trim());
 lines.push('Your finding: '+findingChoices[data.finding][0]+' · participant assessment for SMVS review');
 if(data.capa) lines.push('CAPA status: '+capaStatuses[data.capa]);
 if(!$('packshot-control').hidden||data.photo){
  lines.push('Packshot: '+(data.photo?'Filename selected only · '+data.photo:'Not supplied'));
 }
 return lines.join('\n');
}
function availableFindings(){
 if(!isMah) return endUserFindings;
 if(data.otherCause) return ['on_my_side'];
 if(data.comparison==='no'||data.technical==='no') return ['on_my_side','investigating'];
 return [data.comparison==='yes'&&data.technical==='yes'?'not_my_side':'investigating'];
}
function syncFinding(){
 if(isMah){
  const showFollowUp = Boolean(mahChecks(active))&&data.comparison==='yes';
  $('technical-check').hidden=!showFollowUp;
  $('technical-check').disabled=!showFollowUp;
  if(!showFollowUp){
   data.technical='';
   document.querySelectorAll('input[name="technical"]').forEach(input=>input.checked=false);
  }
 }
 renderGuidance();
 const available=availableFindings();
 for(const input of document.querySelectorAll('input[name="finding"]')){
  input.closest('label').hidden=isMah?['process_error','technical_error','other_error'].includes(input.value):input.value==='on_my_side';
  input.disabled=!available.includes(input.value);
  if(input.disabled) input.checked=false;
 }
 $('finding-hint').textContent=isMah?findingChoices[available[0]][1]:'SMVS will review your finding.';
 if(isMah&&available.length===2){
  $('finding-hint').textContent='Report an issue on your side if the checks establish the cause. You can also send an interim update.';
 }
 if(data.finding&&!available.includes(data.finding)){
  data.finding='';
  $('finding-change').textContent='A check changed. Select your finding again.';
  $('finding-change').hidden=false;
 }
 syncCorrective();
}
function syncCorrective(){
 const onMySide=ownSideFindings.has(data.finding);
 const showComment=isMah?data.otherCause:data.finding==='other_error';
 $('other-comment-field').hidden=!showComment;
 $('other-comment').disabled=!showComment;
 const measures=$('own-measures');
 measures.hidden=!onMySide;
 measures.disabled=!onMySide;
 if(!onMySide){
  data.capa='';
  measures.querySelectorAll('input').forEach(input=>input.checked=false);
 }
}
const auditReports = {
 a7: {
  id: 'DEMO-RPT-7',
  retrieved: '2026-11-10 09:00 UTC',
  events: [
   ['2026-11-09 10:00:00', 'Active → Exported', 'Demo location'],
   ['2026-11-09 10:00:03', 'Repeat Export rejected · A7', 'Demo location']
  ]
 },
 a24: {
  id: 'DEMO-RPT-24',
  retrieved: '2026-11-11 10:00 UTC',
  events: [
   ['2026-09-01 15:52:25', 'Pack created', 'EU · DEMO-1171'],
   ['2026-11-11 08:15:00', 'Active → Destroyed', 'Other location · ID not shared'],
   ['2026-11-11 09:42:00', 'Supply rejected · A24', 'Demo location']
  ]
 }
};
function renderAudit(key){
 const report=auditReports[key];
 const sequence=$('audit-sequence');
 const rows=$('report-events');
 $('report-dialog').close();
 $('audit-empty').hidden=Boolean(report);
 $('open-report').hidden=!report;
 sequence.hidden=!report;
 sequence.replaceChildren();
 rows.replaceChildren();
 if(!report) return;

 const {batch,serial}=scenarios[key];
 $('report-pack').textContent=`Example medicinal product · Batch ${batch} · Serial ${serial}`;
 $('report-meta').textContent=`Fictional report ${report.id} · retrieved ${report.retrieved}`;
 for(const [time,event,location] of report.events){
  const step=el('li');
  step.append(el('strong',event),el('span',time+' UTC'),el('span','Location: '+location));
  sequence.append(step);
  const row=el('tr');
  row.append(el('td',time),el('td',event),el('td',location));
  rows.append(row);
 }
}
function updateResolvedAction(){
 const disputed=$('resolved-not-mine').checked;
 const status=$('commitment-form').elements.namedItem('resolved-capa');
 $('resolved-capa').disabled=disputed;
 if(disputed) status.forEach(input=>input.checked=false);
 $('save-commitment').hidden=!disputed&&!status.value;
 $('commitment-receipt').hidden=true;
}
$('resolved-capa').addEventListener('change',updateResolvedAction);
$('resolved-not-mine').addEventListener('change',updateResolvedAction);
$('commitment-form').addEventListener('submit',event=>{
 event.preventDefault();
 const disputed=$('resolved-not-mine').checked;
 const status=$('commitment-form').elements.namedItem('resolved-capa').value;
 if(!disputed&&!status) return;
 messages.push(disputed
  ? 'Root cause not on my side · End-user assessment for SMVS review.'
  : 'CAPA status: '+capaStatuses[status]);
 renderMessages();
 $('commitment-receipt').textContent='Update recorded in this preview for SMVS review.';
 $('commitment-receipt').hidden=false;
 $('save-commitment').hidden=true;
});
$('guided-form').addEventListener('change',event=>{
 const {name,value}=event.target;
 if(['source','comparison','technical'].includes(name)){
  data[name]=value;
  if(name==='comparison'&&value==='not_checked'){
   data.photo='';
   $('photo-file').value='';
   $('photo-label').textContent='Optional';
  }
  syncFinding();
 }
 if(name==='finding'){
  data.finding=value;
  $('finding-change').hidden=true;
  syncCorrective();
 }
});
$('other-cause').addEventListener('change',event=>{
 data.otherCause=event.target.checked;
 if(!data.otherCause){
  data.comment='';
  $('other-comment').value='';
 }
 syncFinding();
});
$('other-comment').addEventListener('input',event=>data.comment=event.target.value);
$('own-measures').addEventListener('change',event=>data.capa=event.target.value);
$('photo-button').addEventListener('click',()=>$('photo-file').click());
$('photo-file').addEventListener('change',()=>{data.photo=$('photo-file').files[0]?.name||'';$('photo-label').textContent=data.photo?'Selected: '+data.photo+' · not uploaded':'Optional';});
$('guided-form').addEventListener('submit',e=>{e.preventDefault();if(!availableFindings().includes(data.finding)){syncFinding();return;}messages.push(summary());renderMessages();$('guided-form').hidden=true;$('review-state').hidden=false;$('guided-title').textContent='Awaiting SMVS review';});
$('amend').addEventListener('click',()=>{$('review-state').hidden=true;$('guided-form').hidden=false;renderStep();});
$('open-report').addEventListener('click',()=>$('report-dialog').showModal());$('close-report').addEventListener('click',()=>$('report-dialog').close());
$('open-conversation').addEventListener('click',()=>{$('conversation').showModal();$('message').focus();});$('close-conversation').addEventListener('click',()=>$('conversation').close());
$('message-form').addEventListener('submit',e=>{e.preventDefault();const value=$('message').value.trim();if(!value)return;messages.push(value);renderMessages();$('message-form').reset();$('message-receipt').textContent='Message recorded in this preview only.';$('message-receipt').hidden=false;});
$('scenario').addEventListener('change',e=>{setScenario(e.target.value);document.querySelector('.preview details').open=false;});
if(isMah){
 $('viewer-name').textContent='Example Pharma AG';
 $('viewer-context').textContent='MAH';
 $('location-contact').hidden=true;
 $('pack-handling').hidden=true;
}
renderRadioOptions('guided-capa',capaStatuses,true);
renderRadioOptions('resolved-capa',capaStatuses);
const requestedScenario = previewParams.get('scenario');
const initialScenario = Object.hasOwn(scenarios, requestedScenario) ? requestedScenario : 'a3';
$('scenario').value = initialScenario;
setScenario(initialScenario);
