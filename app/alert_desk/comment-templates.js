// Personal server-owned templates. Editor controls intentionally have no form names.
const panel = document.querySelector('[data-template-url]');
if (panel) {
  const form = panel.closest('form');
  const comment = document.querySelector('#comment');
  const choice = panel.querySelector('#comment-template');
  const status = panel.querySelector('#template-status');
  const editor = panel.querySelector('#template-editor');
  const name = panel.querySelector('#template-name');
  const text = panel.querySelector('#template-text');
  const save = panel.querySelector('#template-save');
  const remove = panel.querySelector('#template-delete');
  const insert = panel.querySelector('#template-insert');
  const create = panel.querySelector('#template-create');
  const manage = panel.querySelector('#template-manage');
  let templates = [], editing = null, busy = false, position = 0;
  const url = panel.dataset.templateUrl;
  comment.addEventListener('blur', () => { position = comment.selectionStart; });
  function sync() {
    for (const button of panel.querySelectorAll('button')) button.disabled = busy;
    choice.disabled = busy;
    insert.disabled = busy || !choice.value;
    create.disabled = busy || !comment.value.trim();
    remove.disabled = busy || !editing;
  }
  async function request(path='', body=null) {
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),10000);
    try {
      const response = await fetch(url+path, {signal:controller.signal,...(body ? {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body),
      } : {})});
      const data = await response.json().catch(()=>({}));
      if (!response.ok) throw Error(typeof data.detail==='string' ? data.detail : 'The template action could not be completed.');
      return data;
    } catch(error) {
      if (error.name==='AbortError') throw Error('Templates are temporarily unavailable. You can still write and submit your comment.');
      throw error;
    } finally {clearTimeout(timer);}
  }
  async function run(action) {
    if (busy || form.querySelector('button[type=submit]').disabled) return;
    busy=true;form.dataset.templateBusy='true';sync();status.textContent='Loading …';
    try { await action(); }
    catch (error) { status.textContent=error.message; }
    finally { busy=false;delete form.dataset.templateBusy;sync(); }
  }
  async function load(selected='') {
    const data=await request();templates=data.templates;
    choice.replaceChildren(new Option(templates.length ? 'Choose a template' : 'No templates yet',''));
    for (const item of templates) choice.add(new Option(item.name,String(item.id)));
    choice.value=String(selected);
    status.textContent=templates.length ? `${templates.length} personal templates. Insert adds text to your draft; it does not send it.` : 'No templates yet. Write a comment, then choose Save as template.';
  }
  function edit(item) {
    editing=item;name.value=item?.name || '';text.value=item?.text || comment.value.trim();
    save.textContent=item ? 'Save template changes' : 'Save new template';
    editor.open=true;sync();name.focus();
  }
  function closeEditor() {
    editing=null;name.value='';text.value='';save.textContent='Save new template';editor.open=false;sync();
  }
  choice.addEventListener('change',sync);
  comment.addEventListener('input',sync);
  panel.querySelector('#template-reload').addEventListener('click',()=>run(()=>load(choice.value)));
  create.addEventListener('click',()=>edit(null));
  manage.addEventListener('click',()=>run(async()=>{
    if (!choice.value) {edit(null);status.textContent='Choose a saved template to edit it, or enter a new name and text.';return;}
    const data=await request('/'+choice.value);edit(data.template);status.textContent='Edit the name or text, then save. Previously submitted comments stay unchanged.';
  }));
  panel.querySelector('#template-cancel').addEventListener('click',()=>closeEditor());
  save.addEventListener('click',()=>run(async()=>{
    if (!name.value.trim() || !text.value.trim()) {status.textContent='Enter a template name and text.';return;}
    const data=await request('',{command:editing ? 'update' : 'create',name:name.value.trim(),text:text.value.trim(),
      ...(editing ? {template_id:editing.id,version:editing.version} : {})});
    closeEditor();await load(data.template.id);status.textContent='Template saved. Your comment draft has not changed.';
  }));
  remove.addEventListener('click',()=>{
    if (!editing || !window.confirm('Delete this template? Previously submitted comments stay unchanged.')) return;
    run(async()=>{await request('',{command:'delete',template_id:editing.id,version:editing.version});
      closeEditor();await load();status.textContent='Template deleted. Previously submitted comments stay unchanged.';});
  });
  insert.addEventListener('click',()=>run(async()=>{
    const selected=templates.find(t=>String(t.id)===choice.value);
    if (!selected) return;
    const detail=(await request('/'+selected.id)).template;
    if (detail.version!==selected.version) throw Error('This template changed. Reload the list before inserting it.');
    if (comment.value.length+detail.text.length>comment.maxLength) throw Error('The combined comment exceeds 1,000 characters. Shorten the draft before inserting.');
    const data=await request('',{command:'insert',template_id:selected.id,version:selected.version});
    // The participant may have continued typing during the request. Recheck now.
    if (comment.value.length+data.template.text.length>comment.maxLength) throw Error('The combined comment exceeds 1,000 characters. Shorten the draft before inserting.');
    const at=Math.min(position,comment.value.length);
    // Do not replace selected draft text. Insert before it at the remembered caret.
    comment.setRangeText(data.template.text,at,at,'end');position=comment.selectionStart;
    comment.dispatchEvent(new Event('input',{bubbles:true}));comment.focus();
    status.textContent='Template inserted into your editable draft. No finding has been submitted.';
  }));
  run(()=>load());
}
