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
  const startOwnCause = document.querySelector("#start-own-cause");
  startOwnCause?.addEventListener("click", () => {
    form.elements.own_cause.value = "true";
    document.querySelector("#mah-a24-information").hidden = true;
    document.querySelector("#guided-title").textContent = "Your investigation";
    form.hidden = false;
    form.querySelector("input[type=radio]")?.focus();
  });
  const capa = document.querySelector("#own-measures");
  const comment = document.querySelector("#comment");
  const reviewComment = document.querySelector("#review-comment");
  const reviewCommentText = document.querySelector("#review-comment-text");
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
  const uploadGuidance = document.querySelector("#upload-finding-guidance");
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
      if (uploadGuidance) {
        if (other) {
          uploadGuidance.textContent = 'You selected “Other issue on my side”. Select “Root cause on my side”, or “Still investigating” while you check.';
        } else if (batch === "no" || serial === "no") {
          uploadGuidance.textContent = batch === "no"
            ? 'You indicated that this batch was not uploaded. Select “Root cause on my side”, or “Still investigating” while you check.'
            : 'You indicated that this serial number was not accepted in the upload. Select “Root cause on my side”, or “Still investigating” while you check.';
        } else if (batch !== "yes") {
          uploadGuidance.textContent = 'To select “Root cause not on my side”, first confirm “Yes” to “Was this batch uploaded?” above.';
        } else if (serialCheck && serial !== "yes") {
          uploadGuidance.textContent = 'The batch was uploaded. Now confirm whether this serial number was accepted in the upload. “Root cause not on my side” requires “Yes” to both checks.';
        } else {
          uploadGuidance.textContent = 'Upload checks complete. You can now select “Root cause not on my side” if you found no other issue on your side.';
        }
      }
    }

    const finding = form.querySelector('[name="finding"]:checked');
    if (batchButton) {
      batchButton.disabled = submitting || !finding || batchButton.dataset.applied === "yes";
    }
    const ownSide = finding?.hasAttribute("data-own-side");
    capa.hidden = capa.disabled = !ownSide;
    if (!ownSide) capa.querySelectorAll("input").forEach(input => { input.checked = false; });
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
    if (form.dataset.templateBusy) {
      status.textContent = "Wait for the template action to finish, then submit your findings.";
      return;
    }
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
      document.querySelector('#review-finding').textContent = form.querySelector('[name="finding"]:checked').closest('label').textContent.trim();
      const measure = form.querySelector('[name="capa"]:checked');
      const measures = document.querySelector('#review-measures');
      measures.hidden = !measure;
      measures.textContent = measure ? 'Measures · ' + measure.closest('label').textContent.trim() : '';
      form.dispatchEvent(new Event("alert-desk:findings-saved"));
      status.textContent = "";
      reviewCommentText.textContent = comment.value.trim();
      reviewComment.hidden = !reviewCommentText.textContent;
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
