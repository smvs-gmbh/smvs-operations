'use strict';

const byId = id => document.getElementById(id);
const examples = [
  {id: 'DEMO-A2-OPEN', title: 'A2 · Batch not found', date: '2026-11-11', product: 'Example medicinal product', batch: 'DEMO2604', location: 'Demo location', endUser: 'Compare the batch number', mah: 'Check the batch upload', scenario: 'a2-open'},
  {id: 'DEMO-A7-DESTROY', title: 'A7 · Pack already in requested state', date: '2026-11-11', product: 'Example medicinal product', batch: 'DEMO2605', location: 'Demo location', endUser: 'Check for an earlier Destroy transaction', scenario: 'a7-open'},
  {id: 'DEMO-A24-STATE', title: 'A24 · Pack already decommissioned at another location', date: '2026-11-11', product: 'Example medicinal product', batch: 'DEMO2606', location: 'Demo location', endUser: 'Confirm the pack source and check local causes', scenario: 'a24'},
  {id: 'DEMO-A24-IMT', title: 'A24 · Pack already marked as exported', date: '2026-11-11', product: 'Example medicinal product', batch: 'DEMO2609', location: 'Demo location', endUser: 'Confirm the pack source and check local causes', scenario: 'a24-imt'},
  {id: 'DEMO-A52-EXPIRY', title: 'A52 · Expiry date discrepancy', date: '2026-11-11', product: 'Example medicinal product', batch: 'DEMO2607', location: 'Demo location', endUser: 'Compare expiry dates', scenario: 'a52'},
  {id: 'DEMO-A68-BATCH', title: 'A68 · Batch number mismatch', date: '2026-11-11', product: 'Example medicinal product', batch: 'DEMO2608', location: 'Demo location', endUser: 'Compare batch numbers', scenario: 'a68'},
  {id: 'DEMO-A3-BULK', title: 'A3 · Serial number not found', date: '2026-11-10', product: 'Example medicinal product', batch: 'DEMO2601', location: 'Demo location', endUser: 'Compare the pack', mah: 'Check the batch upload', scenario: 'a3'},
  {id: 'DEMO-A3-PMD', title: 'A3 · Serial number not found', date: '2026-11-09', product: 'Example medicinal product', batch: 'DEMO2602', location: 'Demo location', endUser: 'Awaiting MAH findings', mah: 'Check the batch upload', scenario: 'pmd'},
  {id: 'DEMO-A2-DEFERRED', title: 'A2 · Batch not found', date: '2026-11-09', product: 'Example medicinal product', batch: 'DEMO2603', location: 'Demo location', status: 'deferred', scenario: 'a2'},
  {id: 'DEMO-A7-REPEAT', title: 'A7 · Pack already in requested state', date: '2026-11-09', product: 'Example medicinal product', batch: 'DEMO2601', location: 'Demo location', status: 'resolved', scenario: 'a7'},
];
const roleKey = 'smvs-connect-demo-role';
const passkeyKey = 'smvs-connect-demo-passkey-required';
const signInKey = 'smvs-connect-demo-signed-in';
let filter = 'action';
let role = sessionStorage.getItem(roleKey) === 'mah' ? 'mah' : 'end-user';

function element(tag, text, className) {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

function casesForRole() {
  return examples.filter(item => role === 'end-user' || item.mah || item.status === 'deferred').map(item => {
    const nextAction = role === 'mah' ? item.mah : item.endUser;
    let status = item.status || 'action';
    if (role === 'end-user' && item.scenario === 'pmd') status = 'waiting';
    return {...item, status, nextAction};
  });
}

function caseLink(item) {
  const link = element('a', item.title);
  const params = new URLSearchParams({scenario: item.scenario});
  if (role === 'mah') params.set('view', 'mah');
  link.href = '/columns?' + params;
  return link;
}

function renderRow(item) {
  const statusLabels = {action: 'Action required', waiting: 'Waiting', deferred: 'Deferred by rule', resolved: 'Resolved locally'};
  const row = document.createElement('tr');
  const alert = document.createElement('td');
  alert.append(caseLink(item), element('small', item.id + ' · ' + item.date));
  const product = element('td', item.product);
  product.append(element('small', 'Batch ' + item.batch));
  const location = element('td', role === 'mah' ? 'Shared case' : item.location);
  const status = document.createElement('td');
  status.append(element('span', statusLabels[item.status], 'status ' + item.status));
  if (item.nextAction) status.append(element('small', item.nextAction));
  row.append(alert, product, location, status);
  return row;
}

function render() {
  const needsSignIn = sessionStorage.getItem(passkeyKey) === 'on' && sessionStorage.getItem(signInKey) !== 'yes';
  byId('sign-in').hidden = !needsSignIn;
  byId('overview').hidden = needsSignIn;
  byId('perspective').value = role;
  if (needsSignIn) return;

  byId('organisation').textContent = role === 'mah' ? 'Example Pharma AG' : 'Example Healthcare AG · Demo location';
  const items = casesForRole();
  byId('action-count').textContent = String(items.filter(item => item.status === 'action').length);
  const query = byId('search').value.trim().toLowerCase();
  const visible = items.filter(item => {
    const searchable = [item.title, item.id, item.product, item.batch];
    if (role === 'end-user') searchable.push(item.location);
    return (filter === 'all' || item.status === filter) && searchable.join(' ').toLowerCase().includes(query);
  });
  byId('rows').replaceChildren(...visible.map(renderRow));
  byId('empty').hidden = visible.length > 0;
  byId('result-count').textContent = visible.length + (visible.length === 1 ? ' alert' : ' alerts');
  document.querySelectorAll('[data-filter]').forEach(button => {
    button.setAttribute('aria-pressed', String(button.dataset.filter === filter));
  });
}

byId('perspective').addEventListener('change', event => {
  role = event.target.value;
  sessionStorage.setItem(roleKey, role);
  filter = 'action';
  byId('search').value = '';
  render();
});
byId('search').addEventListener('input', render);
document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => {
  filter = button.dataset.filter;
  render();
}));
byId('settings').addEventListener('click', () => {
  byId('require-passkey').checked = sessionStorage.getItem(passkeyKey) === 'on';
  byId('admin-dialog').showModal();
});
byId('save-settings').addEventListener('click', () => {
  sessionStorage.setItem(passkeyKey, byId('require-passkey').checked ? 'on' : 'off');
  sessionStorage.removeItem(signInKey);
  byId('admin-dialog').close();
  render();
});
byId('simulate-sign-in').addEventListener('click', () => {
  sessionStorage.setItem(signInKey, 'yes');
  render();
});
document.querySelectorAll('[data-close]').forEach(button => {
  button.addEventListener('click', () => byId(button.dataset.close).close());
});
render();
