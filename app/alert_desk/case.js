async function post(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || "The request failed. Try again.");
  }
  return response.json();
}

const fragment = window.location.hash.slice(1);
const caseContent = document.querySelector("#case-content");
if (fragment.startsWith("access=")) {
  window.location.replace("/alerts/access#" + fragment.slice("access=".length));
} else if (fragment) {
  window.history.replaceState(null, "", window.location.pathname);
  const status = document.querySelector("#access-status");
  if (caseContent) caseContent.hidden = true;
  status.hidden = false;
  status.textContent = "Opening your invitation…";
  post("/alerts/exchange", {token: fragment})
    .then(() => window.location.replace("/alerts"))
    .catch(error => { status.textContent = error.message; });
}

const form = document.querySelector("#guided-form");
if (form) {
  const capa = document.querySelector("#own-measures");
  const commentField = document.querySelector("#other-comment-field");
  const comment = document.querySelector("#other-comment");
  const hint = document.querySelector("#next-check");
  const status = document.querySelector("#findings-status");
  const review = document.querySelector("#review-state");
  const caseStatus = document.querySelector("#case-status");
  const amend = document.querySelector("#amend");
  const batchButton = form.querySelector("[data-batch-revision]");
  let submitting = false;
  const button = form.querySelector("button[type=submit]");

  const guidance = {
    yes: "Check for a local workflow or software issue.",
    no: "Check manual entry and scanner settings.",
    not_checked: "If the pack becomes available, compare the printed identifier and update your findings.",
  };
  const serialCheck = form.querySelector('[data-upload-check="serial_accepted"]');
  const syncForm = () => {
    if (form.elements.batch_uploaded) {
      const batch = form.elements.batch_uploaded.value;
      if (serialCheck) {
        serialCheck.hidden = serialCheck.disabled = batch !== "yes";
        if (serialCheck.disabled) serialCheck.querySelectorAll("input").forEach(input => { input.checked = false; });
      }
      const serial = form.elements.serial_accepted?.value;
      const other = form.elements.other_issue.checked;
      const allowed = {
        other: other || batch === "no" || serial === "no",
        not_my_side: !other && batch === "yes" && (!serialCheck || serial === "yes"),
        investigating: true,
      };
      form.querySelectorAll('[name="finding"]').forEach(input => {
        input.disabled = !allowed[input.value];
        if (input.disabled) input.checked = false;
      });
    }

    const finding = form.querySelector('[name="finding"]:checked');
    if (batchButton) {
      batchButton.disabled = submitting || !finding || batchButton.dataset.applied === "yes";
    }
    const ownSide = finding?.hasAttribute("data-own-side");
    capa.hidden = capa.disabled = !ownSide;
    if (!ownSide) capa.querySelectorAll("input").forEach(input => { input.checked = false; });
    commentField.hidden = comment.disabled = finding?.value !== "other";
    if (hint) {
      hint.textContent = guidance[form.elements.comparison.value]
        || "Check the scanner, software and any manual entry used for this verification.";
    }
  };
  syncForm();
  form.addEventListener("change", syncForm);
  amend.addEventListener("click", () => {
    form.elements.submission_key.value = crypto.randomUUID();
    review.hidden = true;
    form.hidden = false;
    form.querySelector("input[type=radio]").focus();
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (submitting) return;
    if (form.hasAttribute("data-preview")) {
      status.textContent = event.submitter === batchButton
        ? "Preview only. This action would apply the finding to the matching alerts in this batch."
        : "Preview only. No findings were sent.";
      return;
    }
    const answers = Object.fromEntries(new FormData(form));
    if (event.submitter === batchButton) answers.batch_revision = batchButton.dataset.batchRevision;
    submitting = button.disabled = true;
    if (batchButton) batchButton.disabled = true;
    status.textContent = "Sending…";
    try {
      const receipt = await post(form.getAttribute("action"), answers);
      document.querySelector("#review-message").textContent = receipt.batch_count
        ? `Findings recorded for ${receipt.batch_count} alerts.`
        : "Findings recorded for SMVS review.";
      if (batchButton && receipt.batch_count && answers.finding !== "investigating") {
        batchButton.dataset.applied = "yes";
      }
      if (!caseStatus.hasAttribute("data-smvs-status")) {
        caseStatus.textContent = answers.finding === "investigating" ? "Still investigating" : "Awaiting SMVS review";
      }
      status.textContent = "";
      form.hidden = true;
      review.hidden = false;
      amend.focus();
    } catch (error) {
      status.textContent = error.message;
    } finally {
      submitting = button.disabled = false;
      syncForm();
    }
  });
}
