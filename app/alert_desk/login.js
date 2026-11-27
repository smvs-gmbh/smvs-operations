const state = document.querySelector('#participant-login-status');
const form = document.querySelector('#participant-signin');
const magic = location.hash.slice(1);
if (magic) history.replaceState(null, '', location.pathname);
if (magic && form) {
  form.hidden = true;
  document.querySelector('#magic-confirmation').hidden = false;
}
const decode = value => Uint8Array.from(atob(value.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
const encode = value => btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
async function post(step, body = {}) {
  const response = await fetch('/alerts/auth/' + step, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || 'Sign-in could not be completed. Try again.');
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
async function loadKeys() {
  const response = await fetch('/alerts/auth/account'); const data = await response.json();
  if (!response.ok) throw new Error('Sign in again to manage your account.');
  const list = document.querySelector('#passkey-list'); list.replaceChildren();
  if (!data.keys.length) { const item = document.createElement('li'); item.textContent = 'No passkey registered for this organisation and role.'; list.append(item); }
  for (const key of data.keys) {
    const item = document.createElement('li'); const text = document.createElement('span');
    text.textContent = `Passkey registered ${key.created_at.replace('T', ' ').replace('Z', ' UTC')}`;
    const button = document.createElement('button'); button.className = 'button'; button.textContent = 'Revoke passkey and sign out';
    button.addEventListener('click', () => {
      if (confirm('Revoke this passkey and sign out all sessions for this organisation and role?')) run(button, async () => { await post('revoke', {key: key.id}); location.replace('/alerts/login'); });
    }); item.append(text, button); list.append(item);
  }
}
document.querySelector('#register-passkey')?.addEventListener('click', event => run(event.target, async () => { await passkey('create'); state.textContent = 'Passkey registered. You can use it for future sign-ins.'; await loadKeys(); }));
document.querySelector('#sign-out')?.addEventListener('click', event => run(event.target, async () => { await post('logout'); location.replace('/alerts/login'); }));
if (document.querySelector('#passkey-list')) loadKeys().catch(error => { state.textContent = error.message; });
