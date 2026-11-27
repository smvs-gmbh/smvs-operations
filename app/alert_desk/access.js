const requestCode = document.querySelector("#request-alert-code");
const verifyCode = document.querySelector("#verify-alert-code");
const status = document.querySelector("#alert-access-status");
const invitation = window.location.hash.slice(1);
if (invitation && requestCode) {
  window.history.replaceState(null, "", window.location.pathname);
  requestCode.hidden = false;
  verifyCode.hidden = true;
  status.textContent = "";
}

async function send(form, payload, destination) {
  const button = form.querySelector("button");
  button.disabled = true;
  status.textContent = "";
  try {
    const response = await fetch(form.action, {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error(response.status === 409
        ? "A code is already active. Check the original tab or wait ten minutes."
        : response.status === 422
          ? "The code is incorrect or has expired."
          : "The request could not be completed. Check your invitation and try again.");
    }
    window.location.replace(destination);
  } catch (error) {
    status.textContent = error.message;
    button.disabled = false;
  }
}

requestCode?.addEventListener("submit", event => {
  event.preventDefault();
  send(requestCode, {token: invitation}, "/alerts/access");
});
verifyCode?.addEventListener("submit", event => {
  event.preventDefault();
  send(verifyCode, {code: verifyCode.elements.code.value}, "/alerts");
});
