document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-upload-form]").forEach((form) => {
    const input = form.querySelector("[data-file-input]");
    const list = form.querySelector("[data-file-list]");
    if (!input || !list) return;

    input.addEventListener("change", () => {
      list.replaceChildren();
      Array.from(input.files || []).forEach((file, index) => {
        const item = document.createElement("div");
        item.className = "selected-file";
        const details = document.createElement("div");
        details.className = "selected-file-name";
        const name = document.createElement("strong");
        name.textContent = file.name;
        const size = document.createElement("span");
        size.textContent = `${(file.size / (1024 * 1024)).toFixed(1)} MB`;
        details.append(name, size);

        const label = document.createElement("label");
        label.className = "field file-description-field";
        label.textContent = "File description";
        const description = document.createElement("textarea");
        description.name = "file_descriptions";
        description.rows = 2;
        description.maxLength = 65535;
        description.setAttribute("aria-label", `Description for ${file.name}`);
        label.append(description);
        item.append(details, label);
        item.dataset.fileIndex = String(index);
        list.append(item);
      });
    });
  });
});
