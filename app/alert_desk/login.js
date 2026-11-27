const state = document.querySelector('#participant-login-status');
const form = document.querySelector('#participant-signin');
const magic = location.hash.slice(1);
if (magic && form) history.replaceState(null, '', location.pathname);
if (magic && form) {
  form.hidden = true;
  document.querySelector('#magic-confirmation').hidden = false;
}
const decode = value => Uint8Array.from(atob(value.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
const encode = value => btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
async function post(step, body = {}) {
  const response = await fetch('/alerts/auth/' + step, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) { const error = new Error(result.detail || 'Sign-in could not be completed. Try again.'); error.status = response.status; throw error; }
  return result;
}
function completed(result) {
  if (result.next) return location.replace(result.next);
  if (result.scopes) {
    form.hidden = true;
    document.querySelector('#magic-confirmation').hidden = true;
    const select = document.querySelector('#signin-scope');
    select.replaceChildren(...result.scopes.map(scope => new Option(scope.label, scope.id)));
    document.querySelector('#scope-choice').hidden = false;
  }
}
async function run(button, work) {
  button.disabled = true; state.textContent = '';
  try { await work(); } catch (error) {
    state.textContent = error.name === 'NotAllowedError' ? 'The passkey request was cancelled or timed out. You can request an email sign-in link instead.' : error.message;
  } finally { button.disabled = false; }
}
async function passkey(mode, body = {}) {
  if (!window.PublicKeyCredential || !window.isSecureContext) throw new Error('Use the configured HTTPS address or localhost in a browser that supports passkeys.');
  const options = await post(mode === 'create' ? 'register-options' : 'options', body);
  options.challenge = decode(options.challenge);
  if (options.user) options.user.id = decode(options.user.id);
  for (const field of ['allowCredentials', 'excludeCredentials']) for (const item of options[field] || []) item.id = decode(item.id);
  const credential = mode === 'create' ? await navigator.credentials.create({publicKey: options}) : await navigator.credentials.get({publicKey: options});
  if (!credential) throw new Error('No passkey was returned.');
  const response = {};
  for (const field of ['clientDataJSON', 'attestationObject', 'authenticatorData', 'signature', 'userHandle']) if (credential.response[field]) response[field] = encode(credential.response[field]);
  return post(mode === 'create' ? 'register-finish' : 'finish', {credential: {id: credential.id, rawId: encode(credential.rawId), type: credential.type, response}});
}
form?.addEventListener('submit', event => {
  event.preventDefault(); const button = event.submitter;
  run(button, async () => {
    const email = form.elements.email.value.trim();
    if (button.value === 'magic') state.textContent = (await post('magic', {email})).message;
    else completed(await passkey('get', {email}));
  });
});
document.querySelector('#consume-magic')?.addEventListener('click', event => run(event.target, async () => completed(await post('consume', {token: magic}))));
document.querySelector('#choose-scope')?.addEventListener('click', event => run(event.target, async () => completed(await post('scope', {scope: Number(document.querySelector('#signin-scope').value)}))));
async function accountData() {
  const response = await fetch('/alerts/auth/account');
  if (!response.ok) throw new Error('Sign in again to manage your account.');
  return response.json();
}
async function readyForChange() {
  const data = await accountData();
  if (data.can_manage) return true;
  document.querySelector('#reauth-required').hidden = false;
  document.querySelector('#reauth-link').focus();
  return false;
}
async function loadKeys() {
  const data = await accountData();
  const list = document.querySelector('#passkey-list'); list.replaceChildren();
  document.querySelector('#passkey-summary').textContent = data.keys.length ? 'Passkey configured' : 'No passkey configured';
  document.querySelector('#register-passkey').textContent = data.keys.length ? 'Add another passkey' : 'Add passkey';
  for (const key of data.keys) {
    const item = document.createElement('li'); const text = document.createElement('span');
    text.textContent = `Added ${key.created_at.slice(0, 10)}`;
    const button = document.createElement('button'); button.className = 'account-revoke'; button.textContent = 'Revoke…';
    button.setAttribute('aria-label', `Revoke passkey added ${key.created_at}`);
    button.addEventListener('click', () => run(button, async () => {
      if (!await readyForChange()) return;
      if (confirm('Revoke this passkey and sign out all sessions for this organisation and role?')) { await post('revoke', {key: key.id}); location.replace('/alerts/login'); }
    })); item.append(text, button); list.append(item);
  }
}
document.querySelector('#register-passkey')?.addEventListener('click', event => run(event.target, async () => {
  if (!await readyForChange()) return;
  await passkey('create');
  location.replace('/alerts?notice=passkey-added');
}));
document.querySelector('#sign-out')?.addEventListener('click', event => run(event.target, async () => { await post('logout'); location.replace('/alerts/login'); }));
if (document.querySelector('#passkey-list')) loadKeys().catch(error => { state.textContent = error.message; });
const onboarding = document.querySelector('#passkey-onboarding');
if (onboarding) {
  const key = 'alert-desk-passkey-later:' + onboarding.dataset.dismissKey;
  try { onboarding.hidden = sessionStorage.getItem(key) === 'yes'; } catch { /* The prompt remains usable without storage. */ }
  document.querySelector('#passkey-later').addEventListener('click', () => {
    onboarding.hidden = true;
    try { sessionStorage.setItem(key, 'yes'); } catch { /* Hiding for this page is enough. */ }
  });
}
