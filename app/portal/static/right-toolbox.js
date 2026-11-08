// Shared behaviour for view settings and record actions. Forms keep their own
// endpoints, validation and audit handling; this controller only changes layout.
export function rightToolbox({toolbox, opener, close, backdrop, workspace, initialFocus = () => close}) {
    const overlay = window.matchMedia('(max-width: 1399px)');
    const inertNodes = [];
    function updateMode() {
        for (const node of inertNodes.splice(0)) node.inert = false;
        const modal = overlay.matches && !toolbox.hidden;
        if (modal) {
            for (let node = toolbox; node.parentElement && node !== document.body; node = node.parentElement) {
                for (const sibling of node.parentElement.children) {
                    if (sibling !== node && sibling !== backdrop && !sibling.inert) {
                        sibling.inert = true;
                        inertNodes.push(sibling);
                    }
                }
            }
        }
        toolbox.setAttribute('role', overlay.matches ? 'dialog' : 'region');
        if (modal) toolbox.setAttribute('aria-modal', 'true');
        else toolbox.removeAttribute('aria-modal');
        backdrop.hidden = !modal;
        document.body.classList.toggle('crm-toolbox-modal', modal);
    }
    function show(focus = true) {
        toolbox.hidden = false;
        workspace.classList.add('crm-toolbox-open');
        opener.setAttribute('aria-expanded', 'true');
        updateMode();
        if (focus) initialFocus()?.focus();
    }
    function hide(focus = true) {
        toolbox.hidden = true;
        workspace.classList.remove('crm-toolbox-open');
        opener.setAttribute('aria-expanded', 'false');
        updateMode();
        if (focus) opener.focus();
    }
    opener.addEventListener('click', () => toolbox.hidden ? show() : hide());
    close.addEventListener('click', () => hide());
    backdrop.addEventListener('click', () => hide());
    overlay.addEventListener('change', updateMode);
    document.addEventListener('keydown', event => {
        if (toolbox.hidden) return;
        if (event.key === 'Escape') { event.preventDefault(); hide(); }
        if (event.key === 'Tab' && overlay.matches) {
            const focusable = Array.from(toolbox.querySelectorAll('button, input, select, textarea, a[href]'))
                .filter(node => !node.disabled && node.tabIndex !== -1 && node.getClientRects().length);
            const first = focusable[0], last = focusable[focusable.length - 1];
            if (event.shiftKey && (document.activeElement === first || !toolbox.contains(document.activeElement))) {
                event.preventDefault(); last?.focus();
            } else if (!event.shiftKey && (document.activeElement === last || !toolbox.contains(document.activeElement))) {
                event.preventDefault(); first?.focus();
            }
        }
    });
    updateMode();
    return {show, hide};
}
