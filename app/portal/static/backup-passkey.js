const backupForm = document.querySelector('#backup-passkey-form');
const backupFeedback = document.querySelector('#backup-passkey-feedback');

backupForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = backupForm.querySelector('button');
  const message = backupFeedback.querySelector('span');
  const signIn = backupFeedback.querySelector('a');
  button.disabled = true;
  backupFeedback.hidden = true;
  signIn.hidden = true;

  try {
    const response = await fetch(backupForm.getAttribute('action'), {
      method: 'POST',
      mode: 'same-origin',
      credentials: 'same-origin',
      referrerPolicy: 'same-origin',
      headers: {Accept: 'application/json'},
      body: new URLSearchParams(new FormData(backupForm)),
    });
    if (response.status === 401) {
      message.textContent = 'Your session has expired. Sign in again to add a passkey.';
      signIn.hidden = false;
    } else if (response.redirected) {
      message.textContent = 'The running portal returned a redirect instead of starting passkey registration. Restart the portal, then try again.';
    } else if (!response.headers.get('content-type')?.includes('application/json')) {
      message.textContent = 'The portal returned an unexpected response (HTTP ' + response.status + ').';
    } else {
      const result = await response.json();
      if (response.ok && /^\/auth\/login#[A-Za-z0-9_-]{43}$/.test(result.next)) {
        location.assign(result.next);
        return;
      }
      message.textContent = result.detail || 'The passkey request could not be started.';
    }
  } catch {
    message.textContent = 'The portal could not be reached. Reload the page and try again.';
  } finally {
    button.disabled = false;
  }
  backupFeedback.hidden = false;
});
