"use strict";
(() => {
  const category = document.getElementById("cause-category");
  const confidence = document.getElementById("cause-confidence");
  if (!category || !confidence) return;
  function update() {
    document.querySelectorAll(".cause-guidance").forEach(section => {
      const selected = section.dataset.category === category.value;
      section.hidden = !selected;
      section.querySelectorAll("select").forEach(input => { input.disabled = !selected; });
    });
    if (category.value === "unknown") confidence.value = "unassessed";
    Array.from(confidence.options).forEach(option => {
      option.disabled = category.value === "unknown" && option.value !== "unassessed";
    });
  }
  category.addEventListener("change", () => {
    confidence.value = category.value === "unknown" ? "unassessed" : "suspected";
    update();
  });
  update();
  const form = document.getElementById("analysis-form");
  if (!form) return;
  form.addEventListener("input", () => {
    form.querySelectorAll("input, select, textarea").forEach(input => input.setCustomValidity(""));
  });
  form.addEventListener("submit", event => {
    const field = name => form.elements.namedItem(name);
    const fail = (input, message) => {
      event.preventDefault();
      input.setCustomValidity(message);
      input.reportValidity();
    };
    if (confidence.value === "confirmed") {
      if (!field("cause").value.trim()) return fail(field("cause"), "Record the confirmed conclusion.");
      if (!field("findings").value.trim()) return fail(field("findings"), "Record supporting findings and evidence.");
      const checks = Array.from(form.querySelectorAll(`.cause-guidance[data-category="${category.value}"] select`));
      const missing = checks.find(input => input.value === "not_checked");
      if (missing) return fail(missing, "Complete this check before confirming the cause.");
      if (!checks.some(input => input.value === "checked")) return fail(checks[0], "At least one check must be completed.");
    }
    if (event.submitter?.value !== "resolve") return;
    if (!field("review_reason").value.trim()) return fail(field("review_reason"), "Give a resolution reason.");
    if (!field("resolution_basis").value) return fail(field("resolution_basis"), "Choose a resolution basis.");
    if (field("resolution_basis").value === "confirmed_cause" && confidence.value !== "confirmed") return fail(confidence, "Confirm the cause, or choose No further local action required and explain why.");
    const pending = form.dataset.pending === "yes" || field("next_action").value.trim() || field("due_date").value;
    if (pending && !field("complete_pending").checked) return fail(field("complete_pending"), "Confirm that pending follow-up is completed or superseded.");
  });
})();
