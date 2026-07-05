(function () {
    const STAGE = 280;   // crop stage size in CSS pixels
    const OUTPUT = 512;  // exported avatar size in device pixels
    const MIN_ZOOM = 1;
    const MAX_ZOOM = 4;

    function bindAvatarEditor(form) {
        const input = form.querySelector(".avatar-file-input");
        const preview = form.querySelector("[data-avatar-preview]");
        const pickButton = form.querySelector("[data-avatar-pick]");
        const removeButton = form.querySelector("[data-avatar-remove]");
        const removeField = form.querySelector("[data-avatar-remove-field]");
        const removeCheckbox = removeField ? removeField.querySelector("input[type='checkbox']") : null;
        const hint = form.querySelector("[data-avatar-hint]");

        if (!input || !preview || !pickButton) {
            return;
        }

        const initial = preview.dataset.initial || "";
        const defaultHint = hint ? hint.innerHTML : "";

        function showPreviewImage(url) {
            preview.innerHTML = "";
            const img = document.createElement("img");
            img.src = url;
            img.alt = "";
            preview.append(img);
        }

        function showPreviewInitial() {
            preview.textContent = initial;
        }

        function markPhotoChosen(file) {
            const transfer = new DataTransfer();
            transfer.items.add(file);
            input.files = transfer.files;
            if (removeCheckbox) {
                removeCheckbox.checked = false;
            }
            if (removeButton) {
                removeButton.classList.remove("is-hidden");
            }
            pickButton.textContent = "Change photo";
            if (hint) {
                hint.innerHTML = defaultHint;
            }
            showPreviewImage(URL.createObjectURL(file));
        }

        pickButton.addEventListener("click", function () {
            input.value = "";
            input.click();
        });

        input.addEventListener("change", function () {
            const file = input.files && input.files[0];
            if (!file) {
                return;
            }
            openCropper(file, {
                onConfirm: markPhotoChosen,
                onCancel: function () {
                    input.value = "";
                },
            });
        });

        if (removeButton) {
            removeButton.addEventListener("click", function () {
                input.value = "";
                if (removeCheckbox) {
                    removeCheckbox.checked = true;
                }
                showPreviewInitial();
                removeButton.classList.add("is-hidden");
                pickButton.textContent = "Add photo";
                if (hint) {
                    hint.textContent = "Photo will be removed when you save.";
                }
            });
        }
    }

    function openCropper(file, callbacks) {
        const reader = new FileReader();
        reader.onload = function () {
            const image = new Image();
            image.onload = function () {
                mountCropper(image, file, callbacks);
            };
            image.onerror = function () {
                callbacks.onCancel();
            };
            image.src = reader.result;
        };
        reader.onerror = function () {
            callbacks.onCancel();
        };
        reader.readAsDataURL(file);
    }

    function mountCropper(image, file, callbacks) {
        const dpr = window.devicePixelRatio || 1;
        const coverScale = Math.max(STAGE / image.width, STAGE / image.height);
        let zoom = MIN_ZOOM;
        const offset = { x: 0, y: 0 };

        const overlay = document.createElement("div");
        overlay.className = "cropper";
        overlay.setAttribute("role", "dialog");
        overlay.setAttribute("aria-modal", "true");
        overlay.setAttribute("aria-label", "Crop your photo");
        overlay.innerHTML = `
            <div class="cropper__panel">
                <h2 class="cropper__title">Position your photo</h2>
                <p class="cropper__hint">Drag to move, slide to zoom.</p>
                <div class="cropper__stage">
                    <canvas class="cropper__canvas" width="${STAGE * dpr}" height="${STAGE * dpr}"></canvas>
                    <span class="cropper__ring" aria-hidden="true"></span>
                </div>
                <input class="cropper__zoom" type="range" min="${MIN_ZOOM}" max="${MAX_ZOOM}" step="0.01" value="${MIN_ZOOM}" aria-label="Zoom">
                <div class="cropper__actions">
                    <button type="button" class="btn btn--secondary" data-cropper-cancel>Cancel</button>
                    <button type="button" class="btn btn--primary" data-cropper-confirm>Use photo</button>
                </div>
            </div>
        `;

        const canvas = overlay.querySelector(".cropper__canvas");
        const stage = overlay.querySelector(".cropper__stage");
        const zoomInput = overlay.querySelector(".cropper__zoom");
        const cancelButton = overlay.querySelector("[data-cropper-cancel]");
        const confirmButton = overlay.querySelector("[data-cropper-confirm]");
        const ctx = canvas.getContext("2d");

        canvas.style.width = STAGE + "px";
        canvas.style.height = STAGE + "px";

        function clampOffset() {
            const scale = coverScale * zoom;
            const maxX = Math.max(0, (image.width * scale - STAGE) / 2);
            const maxY = Math.max(0, (image.height * scale - STAGE) / 2);
            offset.x = Math.min(maxX, Math.max(-maxX, offset.x));
            offset.y = Math.min(maxY, Math.max(-maxY, offset.y));
        }

        function paint(context, size) {
            const ratio = size / STAGE;
            const scale = coverScale * zoom * ratio;
            const drawW = image.width * scale;
            const drawH = image.height * scale;
            const dx = (size - drawW) / 2 + offset.x * ratio;
            const dy = (size - drawH) / 2 + offset.y * ratio;
            context.clearRect(0, 0, size, size);
            context.drawImage(image, dx, dy, drawW, drawH);
        }

        function render() {
            clampOffset();
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            paint(ctx, STAGE);
        }

        let dragging = false;
        let last = { x: 0, y: 0 };

        function pointerDown(event) {
            dragging = true;
            last = { x: event.clientX, y: event.clientY };
            canvas.setPointerCapture(event.pointerId);
        }

        function pointerMove(event) {
            if (!dragging) {
                return;
            }
            offset.x += event.clientX - last.x;
            offset.y += event.clientY - last.y;
            last = { x: event.clientX, y: event.clientY };
            render();
        }

        function pointerUp(event) {
            dragging = false;
            if (canvas.hasPointerCapture(event.pointerId)) {
                canvas.releasePointerCapture(event.pointerId);
            }
        }

        canvas.addEventListener("pointerdown", pointerDown);
        canvas.addEventListener("pointermove", pointerMove);
        canvas.addEventListener("pointerup", pointerUp);
        canvas.addEventListener("pointercancel", pointerUp);

        zoomInput.addEventListener("input", function () {
            zoom = Number(zoomInput.value) || MIN_ZOOM;
            render();
        });

        function close() {
            document.removeEventListener("keydown", onKey);
            overlay.remove();
        }

        function cancel() {
            close();
            callbacks.onCancel();
        }

        function confirm() {
            const out = document.createElement("canvas");
            out.width = OUTPUT;
            out.height = OUTPUT;
            paint(out.getContext("2d"), OUTPUT);
            out.toBlob(function (blob) {
                if (!blob) {
                    cancel();
                    return;
                }
                const name = (file.name || "avatar").replace(/\.[^.]+$/, "") + ".jpg";
                const cropped = new File([blob], name, { type: "image/jpeg" });
                close();
                callbacks.onConfirm(cropped);
            }, "image/jpeg", 0.9);
        }

        function onKey(event) {
            if (event.key === "Escape") {
                cancel();
            }
        }

        cancelButton.addEventListener("click", cancel);
        confirmButton.addEventListener("click", confirm);
        overlay.addEventListener("pointerdown", function (event) {
            if (event.target === overlay) {
                cancel();
            }
        });
        document.addEventListener("keydown", onKey);

        document.body.append(overlay);
        render();
    }

    document.querySelectorAll("[data-avatar-editor]").forEach(bindAvatarEditor);
}());
