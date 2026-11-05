for (const picker of document.querySelectorAll('.contact-picker')) {
  const dialog = picker.querySelector('dialog');
  const options = [...dialog.querySelectorAll('[data-contact-option]')];
  const search = picker.querySelector('[data-contact-search]');
  const value = picker.querySelector('input[type=hidden]');
  const output = picker.querySelector('output');

  const opener = picker.querySelector('[data-open-contact-picker]');
  opener.addEventListener('click', () => {
    const ids = value.value.split(',');
    for (const option of options) {
      const input = option.querySelector('input');
      input.disabled = false;
      input.checked = ids.includes(input.value);
      option.hidden = false;
    }
    search.value = '';
    dialog.showModal();
    search.focus();
  });

  search.addEventListener('input', () => {
    const query = search.value.trim().toLowerCase();
    for (const option of options) {
      option.hidden = Boolean(option.querySelector('input').value) &&
        !option.textContent.toLowerCase().includes(query);
    }
  });

  dialog.addEventListener('keydown', event => {
    if (event.key === 'Enter' && event.target.tagName !== 'BUTTON') event.preventDefault();
  });
  dialog.addEventListener('close', () => {
    for (const option of options) option.querySelector('input').disabled = true;
  });

  picker.querySelector('[data-apply-contacts]').addEventListener('click', () => {
    const selected = options.filter(option => option.querySelector('input:checked')?.value);
    value.value = selected.map(option => option.querySelector('input').value).join(',');
    const names = selected.map(option => option.querySelector('[data-contact-label]').textContent);
    if (opener.dataset.chooseLabel) {
      const labels = names.length ? names : ['No contact selected'];
      output.replaceChildren(...labels.map(name => {
        const item = document.createElement('span');
        item.className = names.length ? 'contact-chip' : 'subtle';
        item.textContent = name;
        return item;
      }));
      opener.textContent = names.length ? 'Change' : opener.dataset.chooseLabel;
      opener.setAttribute('aria-label', opener.textContent + ' · ' + opener.dataset.contactRole);
    } else {
      output.textContent = names.join(', ') || '—';
    }
    dialog.close();
  });
  picker.querySelector('[data-cancel-contacts]').addEventListener('click', () => dialog.close());
}
