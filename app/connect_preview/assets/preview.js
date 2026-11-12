'use strict';
const $ = selector => document.querySelector(selector);
const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
const messages = $('#messages');
const originalMessages = Array.from(messages.children, item => item.cloneNode(true));
const originalTimeline = Array.from($('#timeline').children, item => item.cloneNode(true));
const findingLabels = {procedural:'A procedural issue in our process',technical:'A technical issue',investigating:'We are still investigating',different:'Our findings differ'};
const originLabels = {unknown:'Not established',end_user:'End User',mah:'MAH',it_supplier:'IT Supplier',system:'NMVS / Hub',multiple:'Multiple parties'};
let draft = null;
let responseCount = 0;
let pending = null;
function activateTab(name, focus=false) {
  for (const tab of tabs) {
    const active = tab.getAttribute('aria-controls') === name;
    tab.setAttribute('aria-selected', String(active)); tab.tabIndex = active ? 0 : -1;
    $('#' + tab.getAttribute('aria-controls')).hidden = !active;
    if (active && focus) tab.focus();
  }
}
for (const tab of tabs) {
  tab.addEventListener('click', () => activateTab(tab.getAttribute('aria-controls')));
  tab.addEventListener('keydown', event => {
    let index = tabs.indexOf(tab);
    if (event.key === 'ArrowRight') index = (index+1)%tabs.length;
    else if (event.key === 'ArrowLeft') index = (index-1+tabs.length)%tabs.length;
    else if (event.key === 'Home') index=0;
    else if (event.key === 'End') index=tabs.length-1;
    else return;
    event.preventDefault(); activateTab(tabs[index].getAttribute('aria-controls'),true);
  });
}
for (const button of document.querySelectorAll('[data-open-tab]')) button.addEventListener('click',()=>{activateTab(button.dataset.openTab,true);$('.tabs').scrollIntoView({block:'start'});});
function feedback(text) { $('#feedback').textContent=text;$('#feedback').hidden=false; }
function finding() { return document.querySelector('input[name="finding"]:checked')?.value || ''; }
function capture() {return {finding:finding(),origin:$('#origin').value,corrective:$('#corrective').checked,findings:$('#findings').value.trim(),measures:$('#measures').value.trim()};}
for (const radio of document.querySelectorAll('input[name="finding"]')) radio.addEventListener('change',()=>{
  $('#origin-row').hidden=false;$('#form-error').hidden=true;
  $('#origin').value=radio.value==='procedural'?'end_user':'unknown';$('#origin').disabled=radio.value==='procedural';
});
function reviewRow(label,value) { const row=document.createElement('div');const dt=document.createElement('dt');const dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;row.append(dt,dd);return row; }
$('#response-form').addEventListener('submit',event=>{
  event.preventDefault();pending=capture();
  if (!pending.finding) {$('#form-error').hidden=false;document.querySelector('input[name="finding"]').focus();return;}
  const rows=[reviewRow('Your finding',findingLabels[pending.finding]),reviewRow('Origin · your assessment',originLabels[pending.origin]),reviewRow('Corrective measures',pending.corrective?'Will be taken — commitment recorded':'No commitment recorded')];
  if(pending.findings)rows.push(reviewRow('Additional findings',pending.findings));
  if(pending.measures)rows.push(reviewRow('Corrective measures / comments',pending.measures));
  $('#review-summary').replaceChildren(...rows);$('#review-dialog').showModal();$('#confirm-response').focus();
});
$('#back-to-edit').addEventListener('click',()=>$('#review-dialog').close());
function timeLabel(){return new Date().toISOString().slice(0,16).replace('T',' ')+' UTC';}
function appendMessage(author,type,paragraphs) {
  const article=document.createElement('article');article.className='card message';
  const meta=document.createElement('div');meta.className='message-meta';
  const avatar=document.createElement('span');avatar.className='avatar participant';avatar.textContent='EW';avatar.setAttribute('aria-hidden','true');
  const details=document.createElement('div');const strong=document.createElement('strong');strong.textContent=author;const time=document.createElement('span');time.textContent=timeLabel();details.append(strong,time);
  const tag=document.createElement('span');tag.className='message-type';tag.textContent=type;
  meta.append(avatar,details,tag);article.append(meta);
  for(const text of paragraphs){const p=document.createElement('p');p.textContent=text;article.append(p);}
  messages.append(article);$('#update-count').textContent=String(messages.children.length);
}
$('#confirm-response').addEventListener('click',()=>{
  if(!pending)return;
  const data=pending;pending=null;responseCount++;
  const parts=[findingLabels[data.finding]+'\nOrigin · our assessment: '+originLabels[data.origin],data.corrective?'Corrective measures will be taken. This records a commitment, not completed action.':'No corrective-measures commitment recorded.'];
  if(data.findings)parts.push('Additional findings\n'+data.findings);
  if(data.measures)parts.push('Corrective measures / comments\n'+data.measures);
  appendMessage('Example Wholesale AG · Demo contributor',responseCount===1?'Finding':'Updated finding',parts);
  $('#review-dialog').close();$('#response-card').hidden=true;$('#response-received').hidden=false;
  $('#case-status').textContent='Awaiting SMVS review';$('#case-status').classList.add('review');
  $('#step-response').classList.remove('current');$('#step-review').classList.add('current');
  feedback('Response shared in this preview. SMVS review is the next step. No live message was sent.');$('#response-received').setAttribute('tabindex','-1');$('#response-received').focus();
});
$('#amend').addEventListener('click',()=>{$('#response-card').hidden=false;$('#response-received').hidden=true;document.querySelector('input[name="finding"]:checked')?.focus();feedback('Add or amend your findings. A new submission adds an update and keeps the earlier response visible.');});
$('#save-draft').addEventListener('click',()=>{draft=capture();feedback('Draft kept in this preview tab. Nothing has been shared; reloading or resetting clears it.');});
$('#send-message').addEventListener('click',()=>{const value=$('#message').value.trim();if(!value){feedback('Enter a message before sharing an update.');$('#message').focus();return;}appendMessage('Example Wholesale AG · Demo contributor','Update',[value]);$('#message').value='';feedback('Update added to this preview. Nothing was delivered to a live service.');});
$('#jump-response').addEventListener('click',()=>{const target=$('#response-card').hidden?$('#response-received'):$('#response-card');target.scrollIntoView({block:'start'});target.setAttribute('tabindex','-1');target.focus({preventScroll:true});});
$('#help').addEventListener('click',()=>$('#help-dialog').showModal());$('#close-help').addEventListener('click',()=>$('#help-dialog').close());
for(const dialog of document.querySelectorAll('dialog'))dialog.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();dialog.close();}});
function setChecks(items){$('#check-summary').replaceChildren(...items.map(([text,warning])=>{const span=document.createElement('span');span.textContent=text;if(warning)span.className='warning';return span;}));}
function reset() {
  const serial=$('#scenario').value==='serial';
  draft=null;pending=null;responseCount=0;$('#response-form').reset();$('#origin-row').hidden=true;$('#origin').disabled=false;
  $('#response-card').hidden=false;$('#response-received').hidden=true;$('#feedback').hidden=true;$('#form-error').hidden=true;$('.optional-details').open=false;$('#message').value='';
  $('#case-status').textContent='Your response requested';$('#case-status').classList.remove('review');$('#step-response').classList.add('current');$('#step-review').classList.remove('current');
  messages.replaceChildren(...originalMessages.map(node=>node.cloneNode(true)));$('#update-count').textContent='2';
  $('#history-title').textContent=serial?'Evidence available so far':'Pack history at a glance';
  $('#procedural-hint').textContent=serial?'For example, a value was entered incorrectly.':'For example, the operation was requested again.';
  $('#alert-code').textContent=serial?'A3':'A7';$('#alert-reference').textContent=serial?'Alert DEMO-A3-001':'Alert DEMO-A7-001';
  $('#alert-title').textContent=serial?'Pack not found':'Pack already in the requested state';
  $('#alert-description').textContent=serial?'The submitted serial was not found. Compare the transmitted value with the physical pack.':'An Export request was rejected because the pack was already marked Exported.';
  $('#pack-serial').textContent=serial?'DEMO00000001':'DEMO0000000001';$('#serial-length').textContent=$('#pack-serial').textContent.length+' characters';$('#pack-operation').textContent=serial?'Verify':'Export';
  $('#analysis-title').textContent=serial?'The transmitted serial is shorter than the reference.':'The same operation was requested twice.';
  $('#analysis-detail').textContent=serial?'The submitted serial contains 12 characters; the exact-batch Snapshot reference expects 14. This identifies a discrepancy, not its cause. Please compare it with the printed serial.':'The report records a successful Export and a rejected repeat three seconds later, for the same pack at the same reported location.';
  if(serial){
    setChecks([['✓ Exact batch found',false],['! Serial length differs · 12 / 14',true],['Physical-pack comparison needed',true]]);
    const li=document.createElement('li');const icon=document.createElement('span');icon.className='timeline-icon alert';icon.textContent='!';icon.setAttribute('aria-hidden','true');const title=document.createElement('strong');title.textContent='Verification rejected';const time=document.createElement('time');time.textContent='2026-11-09 10:00:03';const note=document.createElement('small');note.textContent='No pack history requested for this submitted identifier';li.append(icon,title,time,note);$('#timeline').replaceChildren(li);
    $('#evidence-message').textContent='The retained exact-batch reference shows a serial-length discrepancy. Pack history was not requested for the possibly misread serial; comparison with the physical pack comes first.';
  } else {
    setChecks([['✓ Exact batch found',false],['✓ Serial length matches reference',false],['✓ Same reported location',false]]);$('#timeline').replaceChildren(...originalTimeline.map(node=>node.cloneNode(true)));
  }
  activateTab('investigation');
}
$('#scenario').addEventListener('change',reset);$('#reset').addEventListener('click',reset);
