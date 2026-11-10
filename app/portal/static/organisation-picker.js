'use strict';

for (const picker of document.querySelectorAll('[data-organisation-picker]')) {
  const dialog = picker.querySelector('dialog');
  if (!dialog || typeof dialog.showModal !== 'function') continue;
  const value = picker.querySelector('[data-organisation-value]');
  const output = picker.querySelector('[data-organisation-selection]');
  const opener = picker.querySelector('[data-choose-organisation]');
  const search = picker.querySelector('[data-organisation-search]');
  const status = picker.querySelector('[data-organisation-results]');
  const options = Array.from(picker.querySelectorAll('[data-organisation-option]'));
  const normalise = text => text.normalize('NFKD').replace(/\p{M}/gu, '').toLocaleLowerCase().trim();
  const filter = () => {
    const words = normalise(search.value).split(/\s+/).filter(Boolean);
    let count = 0;
    for (const option of options) {
      const input = option.querySelector('input');
      const matches = words.every(word => normalise(option.textContent).includes(word));
      option.hidden = Boolean(input.value) && !matches;
      if (input.value && matches) count++;
    }
    status.textContent = count ? `${count} matching organisation${count === 1 ? '' : 's'}.` : 'No matching organisations in this published Snapshot.';
  };
  picker.querySelector('[data-organisation-fallback]').hidden = true;
  picker.querySelector('[data-organisation-fallback] select').disabled = true;
  value.disabled = false;
  opener.hidden = false;
  opener.addEventListener('click', () => {
    for (const option of options) {
      const input = option.querySelector('input');
      input.disabled = false;
      input.checked = input.value === value.value;
    }
    search.value = '';
    filter();
    dialog.showModal();
    search.focus();
  });
  search.addEventListener('input', filter);
  dialog.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      event.preventDefault();
      dialog.close();
    }
    if (event.key === 'Enter' && event.target.tagName !== 'BUTTON') event.preventDefault();
  });
  dialog.addEventListener('close', () => {
    if (dialog.open) return;
    for (const option of options) option.querySelector('input').disabled = true;
    opener.focus();
  });
  picker.querySelector('[data-cancel-organisation]').addEventListener('click', () => dialog.close());
  picker.querySelector('[data-apply-organisation]').addEventListener('click', () => {
    const option = options.find(item => item.querySelector('input').checked);
    if (option) {
      value.value = option.querySelector('input').value;
      output.textContent = option.querySelector('[data-organisation-label]').textContent;
    }
    dialog.close();
  });
}
