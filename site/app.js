const themeNames = {
  night: "Mongo Night",
  forest: "Emerald Forest",
  ocean: "Midnight Ocean",
  paper: "Mongo Paper",
};

const copyText = async (text) => {
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
};

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

const preview = document.querySelector(".theme-preview");
const previewName = document.getElementById("theme-name");

document.querySelectorAll(".theme-chip").forEach((button) => {
  button.addEventListener("click", () => {
    const theme = button.dataset.theme;
    if (!preview || !theme || !themeNames[theme]) return;

    preview.dataset.previewTheme = theme;
    previewName.textContent = themeNames[theme];

    document.querySelectorAll(".theme-chip").forEach((chip) => {
      const selected = chip === button;
      chip.classList.toggle("active", selected);
      chip.setAttribute("aria-pressed", String(selected));
    });
  });
});
