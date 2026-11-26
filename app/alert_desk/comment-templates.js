// Shared API client; template configuration lives on its own page.
(() => {
  const panel=document.querySelector('[data-template-url]');
  if(!panel)return;
  const library=panel.hasAttribute('data-template-library');
  const form=library ? document.querySelector('#template-editor') : panel.closest('form');
  const status=document.querySelector('#template-status');
  const url=panel.dataset.templateUrl;
  let busy=false;
  async function request(path='',body=null){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);
    try{
      const response=await fetch(url+path,{signal:controller.signal,...(body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {})});
      const data=await response.json().catch(()=>({}));
      if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'The template action could not be completed.');
      return data;
    }catch(error){
      if(error.name==='AbortError')throw Error('Templates are temporarily unavailable. Your comment can still be submitted.');
      throw error;
    }finally{clearTimeout(timer);}
  }
  async function run(action){
    if(busy || (!library && form.querySelector('button[type=submit]').disabled))return;
    busy=true;if(!library)form.dataset.templateBusy='true';
    panel.querySelectorAll('button,select').forEach(b=>{b.disabled=true;});sync();status.textContent='Loading …';
    try{await action();}catch(error){status.textContent=error.message;}
    finally{busy=false;delete form.dataset.templateBusy;panel.querySelectorAll('button,select').forEach(b=>{b.disabled=false;});sync();}
  }
  function savedDraft(){
    try{const value=JSON.parse(sessionStorage.getItem(panel.dataset.draftKey)||'null');
      if(value && typeof value.at==='number' && Date.now()-value.at>=0 && Date.now()-value.at<30*60*1000 && typeof value.comment==='string' && value.comment.length<=1000)return value;
      sessionStorage.removeItem(panel.dataset.draftKey);
    }catch{}
    return null;
  }
  let sync=()=>{};
  if(!library){
    const comment=document.querySelector('#comment'),toggle=panel.querySelector('#template-toggle'),menu=panel.querySelector('#template-menu');
    let position=comment.value.length;
    const fields=['comment','finding','capa','comparison','batch_uploaded','serial_accepted','other_issue','pack_on_hold'];
    function close(){menu.hidden=true;toggle.setAttribute('aria-expanded','false');}
    comment.addEventListener('blur',()=>{position=comment.selectionStart;});
    form.addEventListener('alert-desk:findings-saved',()=>{try{sessionStorage.removeItem(panel.dataset.draftKey);}catch{}});
    window.addEventListener('pageshow',event=>{if(event.persisted){try{sessionStorage.removeItem(panel.dataset.draftKey);}catch{}}});
    document.querySelectorAll('[data-template-navigation]').forEach(link=>link.addEventListener('click',event=>{
      if(form.dataset.templateBusy || form.querySelector('button[type=submit]').disabled){event.preventDefault();status.textContent='Wait for the current action to finish before opening templates.';return;}
      if(link.classList.contains('template-create-link')&&!comment.value.trim()){event.preventDefault();status.textContent='Write a comment first, or create a template on My templates.';return;}
      const values=Object.fromEntries([...new FormData(form)].filter(([key])=>fields.includes(key)));
      try{sessionStorage.setItem(panel.dataset.draftKey,JSON.stringify({at:Date.now(),comment:comment.value,values,editing:!form.hidden,revision:panel.dataset.draftRevision,position}));}
      catch{if(!form.hidden){event.preventDefault();status.textContent='This browser cannot preserve the draft. Copy your comment before leaving the case.';}}
    }));
    const draft=savedDraft();
    if(draft){
      if(draft.editing){
        if(draft.revision===panel.dataset.draftRevision && draft.values){
          for(const control of form.querySelectorAll('input[name]')){
            if(!fields.includes(control.name))continue;
            if(control.type==='radio')control.checked=draft.values[control.name]===control.value;
            else if(control.type==='checkbox')control.checked=Object.hasOwn(draft.values,control.name);
          }
        }
        comment.value=draft.comment;position=Math.min(Number(draft.position)||0,comment.value.length);
        form.elements.submission_key.value=crypto.randomUUID();form.hidden=false;
        document.querySelector('#review-state').hidden=true;form.dispatchEvent(new Event('change',{bubbles:true}));
        status.textContent=draft.revision===panel.dataset.draftRevision?'Your unsubmitted draft has been restored.':'Your comment was restored. The case changed while you were away; review the current findings before submitting.';
      }
      try{sessionStorage.removeItem(panel.dataset.draftKey);}catch{}
    }
    toggle.addEventListener('click',()=>{
      if(!menu.hidden){close();return;}
      menu.hidden=false;toggle.setAttribute('aria-expanded','true');
      run(async()=>{
        const data=await request(),choices=panel.querySelector('#template-choices');choices.replaceChildren();
        for(const item of data.templates){
          const button=document.createElement('button');button.type='button';button.className='template-choice';button.textContent=item.name;
          button.addEventListener('click',()=>run(async()=>{
            const detail=(await request('/'+item.id)).template;
            if(detail.version!==item.version)throw Error('This template changed. Close and reopen the template list.');
            const check=()=>{if(comment.value.length+detail.text.length>comment.maxLength)throw Error('The combined comment exceeds 1,000 characters. Shorten the draft first.');};
            check();const result=await request('',{command:'insert',template_id:item.id,version:item.version});check();
            const at=Math.min(position,comment.value.length);comment.setRangeText(result.template.text,at,at,'end');position=comment.selectionStart;
            comment.dispatchEvent(new Event('input',{bubbles:true}));close();comment.focus();status.textContent='Template inserted into your editable draft.';
          }));choices.append(button);
        }
        if(!data.templates.length){const empty=document.createElement('p');empty.className='investigation-hint';empty.textContent='No saved templates yet.';choices.append(empty);}
        status.textContent='';
      });
    });
    toggle.disabled=false;
    document.addEventListener('click',event=>{if(!panel.contains(event.target))close();});
    document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!menu.hidden){event.preventDefault();close();toggle.focus();}});
  }else{
    const list=document.querySelector('#template-list'),name=document.querySelector('#template-name'),text=document.querySelector('#template-text');
    const save=document.querySelector('#template-save'),remove=document.querySelector('#template-delete'),newButton=document.querySelector('#template-new');
    let editing=null,initial={name:'',text:''};
    const dirty=()=>name.value!==initial.name || text.value!==initial.text;
    const discard=()=>!dirty() || window.confirm('Discard the unsaved template changes?');
    function edit(item=null,seed=''){
      editing=item;name.value=item?.name||'';text.value=item?.text||seed;
      initial={name:name.value,text:text.value};save.textContent=item?'Save template changes':'Save new template';sync();
    }
    sync=()=>{remove.disabled=busy||!editing;newButton.disabled=busy;};
    async function load(selected=''){
      const data=await request();list.replaceChildren(new Option(data.templates.length?'Choose a template':'No templates yet',''));
      for(const item of data.templates)list.add(new Option(item.name,String(item.id)));
      list.value=String(selected);
    }
    list.addEventListener('change',()=>{
      if(!discard()){list.value=editing?String(editing.id):'';return;}
      if(!list.value){edit();return;}
      run(async()=>{const data=await request('/'+list.value);edit(data.template);status.textContent='';});
    });
    newButton.addEventListener('click',()=>{if(discard()){list.value='';edit();name.focus();status.textContent='';}});
    document.querySelector('#template-cancel').addEventListener('click',()=>{edit(editing);status.textContent='Unsaved template changes discarded.';});
    document.querySelector('#template-reload').addEventListener('click',()=>run(async()=>{await load(editing?.id||'');status.textContent='List refreshed. Editor text is unchanged; reopen a template to load its latest version.';}));
    form.addEventListener('submit',event=>{event.preventDefault();run(async()=>{
      if(!name.value.trim()||!text.value.trim()){status.textContent='Enter a template name and text.';return;}
      const result=await request('',{command:editing?'update':'create',name:name.value.trim(),text:text.value.trim(),...(editing?{template_id:editing.id,version:editing.version}:{})});
      edit(result.template);await load(result.template.id);status.textContent='Template saved. Your case draft is unchanged.';
    });});
    remove.addEventListener('click',()=>{
      if(!editing||!window.confirm('Delete this template? Earlier submitted comments stay unchanged.'))return;
      run(async()=>{await request('',{command:'delete',template_id:editing.id,version:editing.version});edit();await load();status.textContent='Template deleted.';});
    });
    document.querySelectorAll('a').forEach(link=>link.addEventListener('click',event=>{if(busy||!discard())event.preventDefault();}));
    run(async()=>{await load();const draft=savedDraft();edit(null,panel.dataset.create==='true'?(draft?.comment||''):'');
      status.textContent=panel.dataset.create==='true'?'Name this template and save. Your comment draft is preserved.':'Select a template to edit, or create a new one.';
    });
  }
})();
