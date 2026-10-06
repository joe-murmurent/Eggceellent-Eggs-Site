document.addEventListener("DOMContentLoaded", () => {
  const chunkSize = 5 * 1024 * 1024;
  const nonMp4VideoExtensions = new Set([".3gp", ".avi", ".m4v", ".mkv", ".mov", ".mpeg", ".mpg", ".webm", ".wmv"]);
  const isUnsupportedVideo = (file) => {
    const extension = file.name.toLowerCase().match(/\.[^.]+$/)?.[0] || "";
    return nonMp4VideoExtensions.has(extension) || (file.type.startsWith("video/") && file.type !== "video/mp4");
  };
  const postChunk = (url, body, onProgress) => new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", url);
    request.withCredentials = true;
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    });
    request.addEventListener("load", () => {
      try {
        resolve({
          ok: request.status >= 200 && request.status < 300,
          status: request.status,
          data: JSON.parse(request.responseText || "{}"),
        });
      } catch {
        reject(new Error("The upload server returned an invalid response."));
      }
    });
    request.addEventListener("error", () => reject(new Error("The file upload failed.")));
    request.send(body);
  });

  const videoViewer = document.querySelector("[data-video-viewer]");
  if (videoViewer) {
    const video = videoViewer.querySelector("[data-video-player]");
    const title = videoViewer.querySelector("[data-video-viewer-title]");
    const closeVideo = () => {
      video.pause();
      video.removeAttribute("src");
      video.load();
    };

    document.querySelectorAll("[data-video-open]").forEach((button) => {
      button.addEventListener("click", () => {
        video.src = button.dataset.videoSrc;
        title.textContent = button.dataset.videoName;
        videoViewer.showModal();
        video.play().catch(() => {});
      });
    });
    videoViewer.querySelector("[data-video-close]").addEventListener("click", () => videoViewer.close());
    videoViewer.addEventListener("close", closeVideo);
    videoViewer.addEventListener("click", (event) => {
      if (event.target === videoViewer) videoViewer.close();
    });
  }

  document.querySelectorAll("[data-upload-form]").forEach((form) => {
    const input = form.querySelector("[data-file-input]");
    const list = form.querySelector("[data-file-list]");
    const status = form.querySelector("[data-upload-status]");
    const formatError = form.querySelector("[data-upload-format-error]");
    const overall = form.querySelector("[data-upload-overall]");
    const overallProgress = form.querySelector("[data-upload-overall-progress]");
    const overallLabel = form.querySelector("[data-upload-overall-label]");
    if (!input || !list) return;

    input.addEventListener("change", () => {
      const hasUnsupportedVideo = Array.from(input.files || []).some(isUnsupportedVideo);
      if (formatError) formatError.hidden = !hasUnsupportedVideo;
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

        const progress = document.createElement("progress");
        progress.max = 100;
        progress.value = 0;
        progress.setAttribute("aria-label", `Upload progress for ${file.name}`);
        const progressText = document.createElement("span");
        progressText.textContent = "Ready";

        const label = document.createElement("label");
        label.className = "field file-description-field";
        label.textContent = "File description";
        const description = document.createElement("textarea");
        description.name = "file_descriptions";
        description.rows = 2;
        description.maxLength = 65535;
        description.setAttribute("aria-label", `Description for ${file.name}`);
        label.append(description);
        item.append(details, progress, progressText, label);
        item.dataset.fileIndex = String(index);
        list.append(item);
      });
    });

    form.addEventListener("submit", async (event) => {
      const allFiles = Array.from(input.files || []);
      if (allFiles.some(isUnsupportedVideo)) {
        event.preventDefault();
        if (formatError) formatError.hidden = false;
        input.focus();
        return;
      }
      const selected = Array.from(input.files || [])
        .map((file, index) => ({ file, index }))
        .filter(({ file }) => file.size > 0);
      const files = selected.map(({ file }) => file);
      if (!files.length) return;

      event.preventDefault();
      const submitButton = form.querySelector('[type="submit"]');
      const selectedFiles = Array.from(list.querySelectorAll(".selected-file"));
      const descriptions = new FormData(form).getAll("file_descriptions");
      const eventData = new FormData(form);
      eventData.delete("files");
      const csrfToken = form.querySelector('[name="csrfmiddlewaretoken"]')?.value;
      const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
      let completedBytes = 0;
      let eventResult;
      if (submitButton) submitButton.disabled = true;
      input.disabled = true;
      if (overall) overall.hidden = false;

      const updateProgress = (progress, progressText, file, fileBytes) => {
        const filePercent = Math.min(100, Math.round((fileBytes / file.size) * 100));
        progress.value = filePercent;
        progressText.textContent = `${filePercent}%`;
        if (overallProgress && overallLabel) {
          const totalPercent = Math.min(100, Math.round(((completedBytes + fileBytes) / totalBytes) * 100));
          overallProgress.value = totalPercent;
          overallLabel.textContent = `${totalPercent}%`;
        }
      };

      try {
        if (!csrfToken) throw new Error("Missing security token.");
        if (status) status.textContent = "Saving event details…";
        const eventResponse = await fetch(form.action || window.location.href, {
          method: "POST",
          body: eventData,
          headers: { "X-Requested-With": "XMLHttpRequest" },
          credentials: "same-origin",
        });
        if (!eventResponse.ok) throw new Error("Could not save the event.");
        eventResult = await eventResponse.json();

        for (const [index, file] of files.entries()) {
          const item = selectedFiles.find((selectedFile) => selectedFile.dataset.fileIndex === String(selected[index].index));
          const progress = item.querySelector("progress");
          const progressText = item.querySelector("span:last-of-type");
          const uploadId = crypto.randomUUID();
          let offset = 0;

          while (offset < file.size) {
            const end = Math.min(offset + chunkSize, file.size);
            const chunkData = new FormData();
            chunkData.append("upload_id", uploadId);
            chunkData.append("offset", String(offset));
            chunkData.append("total_size", String(file.size));
            chunkData.append("file_name", file.name);
            chunkData.append("file_type", file.type || "application/octet-stream");
            chunkData.append("description", descriptions[selected[index].index] || "");
            chunkData.append("csrfmiddlewaretoken", csrfToken);
            chunkData.append("chunk", file.slice(offset, end), file.name);

            const chunkLength = end - offset;
            const chunkResponse = await postChunk(eventResult.upload_url, chunkData, (fraction) => {
              updateProgress(progress, progressText, file, offset + Math.round(chunkLength * fraction));
            });
            if (chunkResponse.status === 409 && Number.isInteger(chunkResponse.data.expected_offset)) {
              offset = chunkResponse.data.expected_offset;
              updateProgress(progress, progressText, file, offset);
              continue;
            }
            if (chunkResponse.data.error === "video-format-not-allowed") {
              throw new Error("video-format-not-allowed");
            }
            if (!chunkResponse.ok) throw new Error("A file upload did not complete.");

            offset = chunkResponse.data.next_offset ?? file.size;
            updateProgress(progress, progressText, file, offset);
            if (status) status.textContent = `Uploading ${file.name}…`;
          }

          completedBytes += file.size;
          progress.value = 100;
          progressText.textContent = "Uploaded";
          if (overallProgress && overallLabel) {
            overallProgress.value = Math.round((completedBytes / totalBytes) * 100);
            overallLabel.textContent = `${overallProgress.value}%`;
          }
        }

        window.location.assign(eventResult.entry_url);
      } catch (error) {
        if (eventResult) {
          if (error.message === "video-format-not-allowed") {
            window.location.assign(`${eventResult.entry_url}?error=video-format-not-allowed`);
            return;
          }
          if (status) status.textContent = "Upload interrupted. The event was saved; return to it to retry unfinished files.";
          window.location.assign(`${eventResult.entry_url}?error=upload-failed`);
        } else {
          if (status) status.textContent = "Could not save the event. Check the details and try again.";
          if (submitButton) submitButton.disabled = false;
          input.disabled = false;
        }
      }
    });
  });
});
