import {rightToolbox} from './right-toolbox.js?v=record-actions-1';
const installed=new WeakMap();
function node(tag,cls,text){const e=document.createElement(tag);e.className=cls||'';if(text)e.textContent=text;return e;}
function button(text){const e=node('button','portal-button portal-button-secondary',text);e.type='button';return e;}
export function installActions(workspace,form,source=null){
    const existing=installed.get(form);
    if(existing){
        if(source){for(const child of [...source.childNodes])if(child.nodeName!=='SUMMARY')existing.body.append(child);source.remove();}
        return existing;
    }
    const opener=button('Actions');
    const aside=node('aside','crm-view-toolbox portal-actions-toolbox');aside.hidden=true;
    aside.id='actions-'+form.dataset.crmFilters;aside.setAttribute('aria-label','Table actions');opener.setAttribute('aria-controls',aside.id);opener.setAttribute('aria-expanded','false');
    const close=button('Close');close.classList.add('secondary-button');close.setAttribute('aria-label','Close actions toolbox');
    const heading=node('div','crm-toolbox-heading');heading.append(node('h2','','Actions'),close);
    const body=node('div','crm-toolbox-body review-form');
    if(source){for(const child of [...source.childNodes])if(child.nodeName!=='SUMMARY')body.append(child);source.remove();}
    aside.append(heading,body);
    const backdrop=button('');backdrop.className='crm-toolbox-backdrop';backdrop.tabIndex=-1;backdrop.hidden=true;backdrop.setAttribute('aria-label','Close actions toolbox');
    workspace.append(backdrop,aside);
    const controller=rightToolbox({toolbox:aside,opener,close,backdrop,workspace});
    // View settings and actions share one workspace but cannot be open together.
    opener.addEventListener('click',()=>{
        const view=workspace.querySelector('.crm-view-toolbox:not(.portal-actions-toolbox)');
        if(view&&!view.hidden)workspace.querySelector('[aria-controls="'+view.id+'"]')?.click();
    }, {capture:true});
    form.addEventListener('click', event=>{
        const toggle=event.target.closest('[aria-controls]');
        const view=workspace.querySelector('.crm-view-toolbox:not(.portal-actions-toolbox)');
        if(toggle&&view&&toggle.getAttribute('aria-controls')===view.id&&!aside.hidden)controller.hide(false);
    }, {capture:true});
    const result={body,opener,aside};installed.set(form,result);
    const place=()=>{const bar=form.querySelector('.crm-view-bar');if(bar&&bar.lastElementChild!==opener)bar.append(opener);};
    place();
    new MutationObserver(()=>{
        const bar=form.querySelector('.crm-view-bar');if(bar&&bar.lastElementChild!==opener)bar.append(opener);
    }).observe(form,{childList:true,subtree:true});
    return result;
}
