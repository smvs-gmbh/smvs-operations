const invitation = location.hash.slice(1);
if (invitation) history.replaceState(null, '', location.pathname);
const mode = invitation ? 'enrol' : 'signin';
const action = document.querySelector('#passkey-action');
const passkeyStatus = document.querySelector('#passkey-status');
if (invitation) {
  document.querySelector('#passkey-title').textContent = 'Register a passkey';
  document.querySelector('#passkey-intro').textContent = 'Use your device or security key to register a passkey for this account.';
  action.textContent = 'Register passkey';
}

function decode(value) {
  return Uint8Array.from(atob(value.replace(/-/g, '+').replace(/_/g, '/')), character => character.charCodeAt(0));
}

function encode(value) {
  return btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function post(step, body) {
  const response = await fetch('/auth/' + mode + '/' + step, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || 'The passkey request failed.');
  return data;
}

action.addEventListener('click', async () => {
  action.disabled = true;
  passkeyStatus.textContent = '';
  try {
    if (!window.PublicKeyCredential || !window.isSecureContext) {
      throw new Error('Open the configured HTTPS address or localhost in a browser that supports passkeys.');
    }
    const options = await post('options', {invitation});
    options.challenge = decode(options.challenge);
    if (invitation) options.user.id = decode(options.user.id);
    for (const key of ['excludeCredentials', 'allowCredentials']) {
      for (const item of options[key] || []) item.id = decode(item.id);
    }
    const credential = invitation
      ? await navigator.credentials.create({publicKey: options})
      : await navigator.credentials.get({publicKey: options});
    if (!credential) throw new Error('No passkey was returned.');
    const response = {};
    for (const key of ['clientDataJSON', 'attestationObject', 'authenticatorData', 'signature', 'userHandle']) {
      if (credential.response[key]) response[key] = encode(credential.response[key]);
    }
    const result = await post('finish', {
      invitation,
      credential: {id: credential.id, rawId: encode(credential.rawId), type: credential.type, response},
    });
    location.replace(result.next);
  } catch (error) {
    passkeyStatus.textContent = error.name === 'NotAllowedError' ? 'The passkey request was cancelled or timed out.' : error.message;
    action.disabled = false;
  }
});
