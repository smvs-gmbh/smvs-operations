const token = location.hash.slice(1);
history.replaceState(null, '', location.pathname);
const action = document.querySelector('#confirm');
const status = document.querySelector('#status');
if (!token) {action.disabled=true;status.textContent='Open the confirmation link from your email.';}
action.addEventListener('click',async()=>{
 action.disabled=true;
 try {
  const response=await fetch('/confirm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
  if(response.status>=500){
   status.textContent='Confirmation is temporarily unavailable. Please try again shortly.';
   action.disabled=false;return;
  }
  if(!response.ok){
   status.textContent='This link is invalid, expired or already used. Please contact SMVS for assistance.';
   return;
  }
  status.textContent='Your email address has been confirmed. Your registration is now awaiting review by SMVS.';
 }catch(error){
  status.textContent='The request could not be completed. Check your connection and try again.';
  action.disabled=false;
 }
});
