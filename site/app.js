const themeLabels = {
  night: "Grove Night",
  evergreen: "Evergreen",
  blue: "Blue Hour",
  paper: "Field Notes",
};

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const fallback = document.createElement("textarea");
  fallback.value = text;
  fallback.setAttribute("readonly", "");
  fallback.style.position = "fixed";
  fallback.style.opacity = "0";
  document.body.append(fallback);
  fallback.select();
  document.execCommand("copy");
  fallback.remove();
}

document.querySelectorAll("[data-copy-target]").forEach((button) => {
  button.addEventListener("click", async () => {
    const target = document.getElementById(button.dataset.copyTarget);
    if (!target) return;

    const originalLabel = button.textContent;
    try {
      await copyText(target.textContent.trim());
      button.textContent = "Copied";
    } catch {
      button.textContent = "Copy failed";
    }

    window.setTimeout(() => {
      button.textContent = originalLabel;
    }, 1600);
  });
});

const themePreview = document.querySelector(".theme-demo");
const themeLabel = document.getElementById("theme-label");

document.querySelectorAll(".theme-choice").forEach((choice) => {
  choice.addEventListener("click", () => {
    const theme = choice.dataset.theme;
    if (!themePreview || !theme || !themeLabels[theme]) return;

    themePreview.dataset.themePreview = theme;
    themeLabel.textContent = themeLabels[theme];

    document.querySelectorAll(".theme-choice").forEach((button) => {
      const selected = button === choice;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
  });
});
