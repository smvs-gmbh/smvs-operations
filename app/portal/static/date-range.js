// Shortcuts fill explicit dates; Apply/Save retain a stable scope across pages/export.
export function validDateRanges(root) {
    return [...root.querySelectorAll('[data-date-range] input:not(:disabled)')]
        .every(control=>control.checkValidity());
}

export function enhanceDateRanges(root) {
    for (const group of root.querySelectorAll('[data-date-range]')) {
        if (group.dataset.dateReady) continue;
        group.dataset.dateReady='true';
        const start=group.querySelector('[name="start"]');
        const end=group.querySelector('[name="end"]');
        const lower=start.min, upper=end.max;
        function validate() {
            start.max=end.value || upper;
            end.min=start.value || lower;
            end.setCustomValidity(start.value && end.value && start.value>end.value
                ? 'Choose an end date on or after the start date.' : '');
        }
        start.addEventListener('change',validate);
        end.addEventListener('change',validate);
        for (const button of group.querySelectorAll('[data-date-start]')) {
            button.addEventListener('click',event=>{
                event.preventDefault();
                start.value=button.dataset.dateStart;
                end.value=button.dataset.dateEnd;
                for (const control of [start,end]) {
                    control.dispatchEvent(new Event('input',{bubbles:true}));
                    control.dispatchEvent(new Event('change',{bubbles:true}));
                }
            });
        }
        validate();
    }
}
