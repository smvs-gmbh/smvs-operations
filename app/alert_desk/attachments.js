const attachmentPanel = document.querySelector('#case-attachments');
if (attachmentPanel) {
  const url = attachmentPanel.dataset.url;
  const list = document.querySelector('#attachment-list');
  const status = document.querySelector('#attachment-status');
  const uploadForm = document.querySelector('#attachment-form');
  let pendingUpload = null;
  async function loadAttachments() {
    const response = await fetch(url);
    if (!response.ok) throw new Error('Attachments could not be loaded. Reload the case.');
    const result = await response.json();
    list.replaceChildren(...result.files.map(file => {
      const row = document.createElement('li');
      const link = document.createElement('a');
      link.href = url + '/' + Number(file.id);
      link.textContent = `${file.filename} →`;
      const detail = document.createElement('span');
      detail.textContent = ` · ${Math.ceil(file.bytes / 1024)} KiB · ${file.at.slice(0, 19).replace('T', ' ') + ' UTC'}`;
      row.append(link, detail); return row;
    }));
    if (!result.files.length) { const row = document.createElement('li'); row.textContent = 'No attachments yet.'; list.append(row); }
  }
  uploadForm?.querySelector('input').addEventListener('change', () => { pendingUpload = null; status.textContent = ''; });
  uploadForm?.addEventListener('submit', async event => {
    event.preventDefault();
    const button = uploadForm.querySelector('button');
    if (button.disabled) return;
    const file = document.querySelector('#attachment-file').files[0];
    if (!file || file.size === 0 || file.size > 5 * 1024 * 1024) { status.textContent = 'Select a non-empty file of at most 5 MiB.'; return; }
    button.disabled = true; status.textContent = 'Uploading…';
    try {
      if (!pendingUpload) {
        const content = await new Promise((resolve, reject) => {
          const reader = new FileReader(); reader.onload = () => resolve(reader.result.split(',')[1]);
          reader.onerror = () => reject(new Error('The selected file could not be read.')); reader.readAsDataURL(file);
        });
        pendingUpload = {submission_key: crypto.randomUUID(), basis: attachmentPanel.dataset.basis, filename: file.name, content};
      }
      const response = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(pendingUpload)});
      if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(error.detail || 'Upload failed. You can retry the same file.'); }
      pendingUpload = null; uploadForm.reset();
      await loadAttachments(); status.textContent = 'File uploaded for SMVS review.';
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  });
  loadAttachments().catch(error => { status.textContent = error.message; });
}
