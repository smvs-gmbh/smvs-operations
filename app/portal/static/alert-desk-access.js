const rows = Array.from(document.querySelectorAll("[data-alert-contact]"));
const selectAll = document.querySelector("#alert-access-all");
const search = document.querySelector("#alert-contact-search");
const statusFilter = document.querySelector("#alert-contact-status");
const send = document.querySelector("#alert-access-send");
const count = document.querySelector("#alert-access-count");

function visibleChoices() {
  return rows.filter(row => !row.hidden)
    .map(row => row.querySelector("input[type=checkbox]"))
    .filter(input => !input.disabled);
}

function syncSelection() {
  const visible = visibleChoices();
  const selected = visible.filter(input => input.checked);
  selectAll.checked = selected.length > 0 && selected.length === visible.length;
  selectAll.indeterminate = selected.length > 0 && selected.length < visible.length;
  selectAll.disabled = visible.length === 0;
  send.elements.selected.value = selected.map(input => input.value).join(",");
  send.querySelector("button").disabled = selected.length === 0;
  count.value = `${selected.length} selected`;
}

function filter() {
  const term = search.value.toLowerCase().trim();
  for (const row of rows) {
    row.hidden = !row.textContent.toLowerCase().includes(term)
      || (statusFilter.value && row.dataset.sent !== statusFilter.value);
    if (row.hidden) row.querySelector("input[type=checkbox]").checked = false;
  }
  syncSelection();
}

selectAll.addEventListener("change", () => {
  for (const input of visibleChoices()) input.checked = selectAll.checked;
  syncSelection();
});
for (const row of rows) row.addEventListener("change", syncSelection);
search.addEventListener("input", filter);
statusFilter.addEventListener("change", filter);
filter();
