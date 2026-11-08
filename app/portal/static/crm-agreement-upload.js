const form = document.querySelector("[data-agreement-upload]");
const fileInput = form.querySelector('input[type="file"]');
const button = form.querySelector('button[type="submit"]');
const status = form.querySelector('[role="status"]');
form.hidden = false;

form.addEventListener("submit", async event => {
    event.preventDefault();
    const file = fileInput.files[0];
    if (!file || button.disabled) return;
    button.disabled = true;
    fileInput.disabled = true;
    status.textContent = "Uploading PDF…";
    try {
        const response = await fetch(form.getAttribute("action"), {
            method: "POST",
            headers: { "X-Filename": encodeURIComponent(file.name) },
            body: file,
        });
        if (response.status !== 204) {
            const error = await response.json().catch(() => null);
            throw new Error(error?.detail || "Upload failed. Check your sign-in and try again.");
        }
        window.location.hash = "agreement-documents";
        window.location.reload();
    } catch (error) {
        status.textContent = error.message;
        button.disabled = false;
        fileInput.disabled = false;
    }
});
