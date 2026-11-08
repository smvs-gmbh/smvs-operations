export function initialiseColumns(form, preference) {
    const table = form.closest("section").querySelector("table[data-crm-columns]");
    if (!table) return;
    const headers = Array.from(table.querySelectorAll("thead th[data-column]"));
    const toolbar = document.createElement("details");
    toolbar.className = "crm-filter-settings";
    const summary = document.createElement("summary");
    summary.textContent = "My columns";
    toolbar.append(summary);
    const explanation = document.createElement("p");
    explanation.className = "subtle";
    explanation.textContent = "Choose and arrange the columns for this directory. Use the arrows to change their order. The record name stays visible.";
    toolbar.append(explanation);
    const options = document.createElement("div");
    options.className = "crm-column-options";
    const keys = headers.map(header => header.dataset.column);
    let order = (preference.column_order || keys).filter(key => keys.includes(key));
    order = [...order, ...keys.filter(key => !order.includes(key))];
    const rows = Array.from(table.rows).map(row => ({
        row,
        cells: Array.from(row.cells),
    }));
    const items = new Map();
    const choices = new Map();
    headers.forEach((header, index) => {
        const label = document.createElement("label");
        label.className = "resolve-confirm";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = index === 0 || (preference.columns
            ? preference.columns.includes(header.dataset.column)
            : header.dataset.defaultVisible !== "false");
        checkbox.disabled = index === 0;
        label.append(checkbox, document.createTextNode(header.textContent.trim()));
        choices.set(header.dataset.column, checkbox);
        checkbox.addEventListener("change", applyColumns);
        const item = document.createElement("div");
        item.className = "crm-column-option";
        item.append(label);
        const moves = document.createElement("div");
        moves.className = "crm-column-moves";
        for (const [direction, symbol] of [[-1, "↑"], [1, "↓"]]) {
            const move = document.createElement("button");
            move.type = "button";
            move.className = "portal-button portal-button-secondary";
            move.textContent = symbol;
            move.setAttribute("aria-label", `Move ${header.textContent.trim()} ${direction < 0 ? "up" : "down"}`);
            move.title = move.getAttribute("aria-label");
            move.addEventListener("click", () => {
                const position = order.indexOf(header.dataset.column);
                const destination = position + direction;
                if (destination < 0 || destination >= order.length) return;
                [order[position], order[destination]] = [order[destination], order[position]];
                applyColumns();
                const focusButton = move.disabled ? item.querySelector("button:not(:disabled)") : move;
                focusButton?.focus({preventScroll: true});
            });
            moves.append(move);
        }
        item.append(moves);
        items.set(header.dataset.column, item);
    });
    function applyColumns() {
        for (const [position, key] of order.entries()) {
            const item = items.get(key);
            options.append(item);
            const buttons = item.querySelectorAll("button");
            buttons[0].disabled = position === 0;
            buttons[1].disabled = position === order.length - 1;
        }
        const visibleCount = Array.from(choices.values()).filter(checkbox => checkbox.checked).length;
        for (const {row, cells} of rows) {
            if (cells.length === 1 && keys.length > 1) {
                cells[0].colSpan = visibleCount;
                continue;
            }
            for (const key of order) {
                const cell = cells[keys.indexOf(key)];
                cell.hidden = !choices.get(key).checked;
                row.append(cell);
            }
        }
        form.dispatchEvent(new CustomEvent("crm-view-change"));
    }
    applyColumns();
    const searchLabel = document.createElement("label");
    searchLabel.className = "crm-column-search";
    searchLabel.append(document.createTextNode("Find a column"));
    const search = document.createElement("input");
    search.type = "search";
    search.placeholder = "Name, email, status…";
    search.addEventListener("input", () => {
        const term = search.value.trim().toLocaleLowerCase();
        for (const item of items.values()) item.hidden = !item.querySelector("label").textContent.toLocaleLowerCase().includes(term);
    });
    searchLabel.append(search);
    toolbar.append(searchLabel, options);
    const actions = document.createElement("div");
    actions.className = "crm-filter-actions";
    const reset = document.createElement("button");
    reset.type = "button";
    reset.className = "portal-button portal-button-secondary";
    reset.textContent = "Reset columns";
    actions.append(reset);
    toolbar.append(actions);
    const note = document.createElement("p");
    note.className = "subtle";
    note.textContent = "Save the selection and order with your view.";
    toolbar.append(note);
    form.append(toolbar);
    reset.addEventListener("click", () => {
        for (const header of headers) choices.get(header.dataset.column).checked = header.dataset.defaultVisible !== "false";
        order = [...keys];
        applyColumns();
    });
    return {
        getState() {
            return {columns: order.filter(key => choices.get(key).checked), column_order: [...order]};
        },
    };
}
