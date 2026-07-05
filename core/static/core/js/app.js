(function () {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (const cookie of cookies) {
      const trimmed = cookie.trim();
      if (trimmed.startsWith(`${name}=`)) {
        return decodeURIComponent(trimmed.slice(name.length + 1));
      }
    }
    return "";
  }

  function csrfHeaders(extra) {
    return Object.assign({
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    }, extra || {});
  }

  function postJson(url, payload) {
    return fetch(url, {
      method: "POST",
      headers: csrfHeaders(),
      body: JSON.stringify(payload || {}),
    });
  }

  function bindLogForms() {
    document.querySelectorAll("form[data-log-form]").forEach((form) => {
      const button = form.querySelector("button[type='submit'], .log-action, .log-circle");
      if (!button) {
        return;
      }

      const label = button.querySelector("[data-log-label], .log-btn__label, .log-circle__label") || button;

      if (!reducedMotion) {
        button.addEventListener("pointerdown", () => {
          button.classList.add("is-pressed");
        });

        ["pointerup", "pointercancel", "pointerleave"].forEach((eventName) => {
          button.addEventListener(eventName, () => {
            button.classList.remove("is-pressed");
          });
        });
      }

      form.addEventListener("submit", () => {
        form.querySelectorAll("button[type='submit']").forEach((submitButton) => {
          submitButton.disabled = true;
        });
        label.textContent = "Logging…";
      });
    });
  }

  let openPicker = null;

  function allowedReactions() {
    const node = document.getElementById("allowed-reactions");
    if (!node) {
      return [];
    }
    try {
      const parsed = JSON.parse(node.textContent);
      return Array.isArray(parsed) ? parsed : [];
    } catch (_error) {
      return [];
    }
  }

  function closePicker() {
    if (!openPicker) {
      return;
    }
    openPicker.replaceWith(openPicker.sourceButton);
    openPicker = null;
    document.dispatchEvent(new Event("live:ready"));
  }

  function appendReactionOption(picker, emoji) {
    const option = document.createElement("button");
    option.type = "button";
    option.className = "reaction-picker__option";
    option.textContent = emoji;
    option.setAttribute("aria-label", `React with ${emoji}`);
    option.dataset.emoji = emoji;
    picker.append(option);
  }

  function renderPickerOptions(picker, expanded) {
    picker.textContent = "";
    picker.classList.toggle("is-expanded", expanded);
    const visible = expanded ? picker.reactions : picker.reactions.slice(0, 6);

    visible.forEach((emoji) => appendReactionOption(picker, emoji));

    if (!expanded && picker.reactions.length > visible.length) {
      const more = document.createElement("button");
      more.type = "button";
      more.className = "reaction-picker__more";
      more.textContent = "+";
      more.setAttribute("aria-label", "More reactions");
      more.dataset.reactionMore = "";
      picker.append(more);
    }
  }

  function pickerMarkup(sourceButton) {
    const picker = document.createElement("div");
    picker.className = "reaction-picker";
    picker.dataset.reactionPicker = "";
    picker.sourceButton = sourceButton;
    picker.reactions = allowedReactions();
    renderPickerOptions(picker, false);

    return picker;
  }

  function responseHtml(response) {
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return response.json().then((data) => data.html || data.reaction_row_html || data.reactions_html || "");
    }
    return response.text();
  }

  function submitReaction(row, url, emoji) {
    if (!url || !row || !emoji) {
      window.location.reload();
      return;
    }

    postJson(url, { emoji })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Reaction failed.");
        }
        return responseHtml(response);
      })
      .then((html) => {
        if (!html.trim()) {
          window.location.reload();
          return;
        }
        row.outerHTML = html;
        openPicker = null;
        document.dispatchEvent(new Event("live:ready"));
      })
      .catch(() => {
        window.location.reload();
      });
  }

  function bindLiveSync() {
    const root = document.querySelector("[data-live-root]");
    if (!root || !root.dataset.liveUrl) {
      return;
    }

    let version = root.dataset.liveVersion || "";
    let pending = false;
    let busy = false;

    function liveControlFocused() {
      const active = document.activeElement;
      return Boolean(active && active.closest("[data-live]") && active.matches("input, textarea, select, button"));
    }

    function blocked() {
      return Boolean(openPicker || liveControlFocused());
    }

    function nextSection(doc, key) {
      return Array.from(doc.querySelectorAll("[data-live]")).find((node) => node.dataset.live === key);
    }

    async function refreshLiveSections() {
      if (blocked()) {
        pending = true;
        return;
      }
      try {
        const response = await fetch(window.location.href, { headers: { "X-Requested-With": "fetch" } });
        if (!response.ok) {
          return;
        }
        const doc = new DOMParser().parseFromString(await response.text(), "text/html");
        if (blocked()) {
          pending = true;
          return;
        }
        document.querySelectorAll("[data-live]").forEach((node) => {
          const next = nextSection(doc, node.dataset.live);
          if (next) {
            node.innerHTML = next.innerHTML;
          }
        });
        const nextRoot = doc.querySelector("[data-live-root]");
        if (nextRoot && nextRoot.dataset.liveVersion) {
          version = nextRoot.dataset.liveVersion;
          root.dataset.liveVersion = version;
        }
        pending = false;
      } catch (_error) {}
    }

    async function checkVersion() {
      if (busy || document.visibilityState !== "visible") {
        return;
      }
      busy = true;
      try {
        const response = await fetch(root.dataset.liveUrl, { headers: { Accept: "application/json" } });
        if (response.ok) {
          const data = await response.json();
          if (data.version && data.version !== version) {
            await refreshLiveSections();
          }
        }
      } catch (_error) {
      } finally {
        busy = false;
      }
    }

    function applyPending() {
      if (pending && !blocked()) {
        refreshLiveSections();
      }
    }

    window.setInterval(checkVersion, 10000);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") {
        checkVersion();
      }
    });
    document.addEventListener("focusout", () => window.setTimeout(applyPending, 0), true);
    document.addEventListener("live:ready", applyPending);
    if (navigator.serviceWorker) {
      navigator.serviceWorker.addEventListener("message", (event) => {
        if (event.data && event.data.type === "refresh") {
          checkVersion();
        }
      });
    }
  }

  function bindReactions() {
    document.addEventListener("click", (event) => {
      const addButton = event.target.closest("[data-reaction-add]");
      const moreButton = event.target.closest("[data-reaction-more]");
      const pickerOption = event.target.closest("[data-reaction-picker] [data-emoji]");
      const toggleButton = event.target.closest("[data-reaction-row] .reaction-pill[data-emoji]");

      if (moreButton && openPicker && openPicker.contains(moreButton)) {
        event.preventDefault();
        event.stopPropagation();
        renderPickerOptions(openPicker, true);
        return;
      }

      if (pickerOption && openPicker) {
        event.preventDefault();
        event.stopPropagation();

        const row = openPicker.closest("[data-reaction-row]") || openPicker.closest(".reaction-row");
        const url = openPicker.sourceButton.dataset.reactionUrl || (row && row.dataset.reactionUrl);
        const emoji = pickerOption.dataset.emoji;

        submitReaction(row, url, emoji);
        return;
      }

      if (toggleButton) {
        event.preventDefault();
        event.stopPropagation();
        if (openPicker) {
          closePicker();
        }

        const row = toggleButton.closest("[data-reaction-row]");
        const url = toggleButton.dataset.reactionUrl || (row && row.dataset.reactionUrl);
        submitReaction(row, url, toggleButton.dataset.emoji);
        return;
      }

      if (addButton) {
        event.preventDefault();
        event.stopPropagation();
        if (openPicker) {
          closePicker();
        }
        const picker = pickerMarkup(addButton);
        addButton.replaceWith(picker);
        openPicker = picker;
        return;
      }

      if (openPicker && !event.target.closest("[data-reaction-picker]")) {
        closePicker();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePicker();
      }
    });
  }

  function checkIcon() {
    return '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m5 12 4 4 10-10" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  }

  function copyText(value) {
    if (!value) {
      return Promise.resolve(false);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(value).then(() => true).catch(() => fallbackCopy(value));
    }
    return fallbackCopy(value);
  }

  function fallbackCopy(value) {
    if (!document.queryCommandSupported || !document.queryCommandSupported("copy")) {
      return Promise.resolve(false);
    }

    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.top = "-999px";
    textarea.style.opacity = "0";
    document.body.append(textarea);
    textarea.select();

    let copied = false;
    try {
      copied = document.execCommand("copy");
    } catch (_error) {
      copied = false;
    }
    textarea.remove();
    return Promise.resolve(copied);
  }

  function bindCopies() {
    document.querySelectorAll("[data-copy]").forEach((button) => {
      const originalHtml = button.innerHTML;
      let timeout = null;

      button.addEventListener("click", (event) => {
        event.preventDefault();
        copyText(button.dataset.copyText || "").then((copied) => {
          if (!copied) {
            return;
          }

          window.clearTimeout(timeout);
          const label = button.querySelector("[data-copy-label]");
          if (label) {
            label.textContent = "Copied ✓";
          } else {
            button.innerHTML = checkIcon();
          }
          button.classList.add("is-copied");

          timeout = window.setTimeout(() => {
            button.innerHTML = originalHtml;
            button.classList.remove("is-copied");
          }, 1500);
        });
      });
    });
  }

  function bindShare() {
    document.querySelectorAll("[data-share-native]").forEach((button) => {
      if (!navigator.share) {
        button.hidden = true;
        return;
      }

      button.addEventListener("click", () => {
        navigator.share({
          title: button.dataset.shareTitle || "",
          text: button.dataset.shareText || "",
          url: button.dataset.shareUrl || "",
        }).catch((error) => {
          if (!error || error.name === "AbortError") {
            return;
          }
        });
      });
    });
  }

  function bindNudges() {
    document.querySelectorAll("[data-nudge]").forEach((button) => {
      const original = button.innerHTML;
      button.addEventListener("click", () => {
        const url = button.dataset.nudgeUrl;
        if (!url || button.disabled) {
          return;
        }

        button.disabled = true;
        postJson(url, {})
          .then((response) => {
            if (!response.ok) {
              throw new Error("Nudge failed.");
            }
            button.innerHTML = checkIcon();
            window.setTimeout(() => {
              button.innerHTML = original;
              button.disabled = false;
              button.classList.remove("is-disabled");
              button.removeAttribute("aria-disabled");
            }, 1500);
          })
          .catch(() => {
            button.disabled = false;
            window.location.reload();
          });
      });
    });
  }

  function setFieldValue(selector, value) {
    if (value === undefined) {
      return;
    }
    const field = document.querySelector(selector);
    if (field) {
      field.value = value;
      field.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  function setCadence(value) {
    if (!value) {
      return;
    }
    const radio = Array.from(document.querySelectorAll("input[name='cadence']")).find((input) => input.value === value);
    if (radio) {
      radio.checked = true;
      radio.dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }
    setFieldValue("[data-project-cadence], select[name='cadence'], #id_cadence", value);
  }

  function applyTemplate(input) {
    setFieldValue("[data-project-name], input[name='name'], #id_name", input.dataset.name || "");
    setFieldValue("[data-project-activity], input[name='activity'], input[name='activity_name'], #id_activity", input.dataset.activity || "");
    setFieldValue("[data-project-unit], input[name='unit'], #id_unit", input.dataset.unit || "");
    setCadence(input.dataset.cadence);
  }

  function bindCreateHelpers() {
    const recapActivity = document.querySelector("[data-recap-activity]");
    const recapUnit = document.querySelector("[data-recap-unit]");
    const recapCadence = document.querySelector("[data-recap-cadence]");
    const recapDuration = document.querySelector("[data-recap-duration]");
    const activityField = document.querySelector("[data-project-activity], input[name='activity'], input[name='activity_name'], #id_activity");
    const unitField = document.querySelector("[data-project-unit], input[name='unit'], #id_unit");
    const endDateField = document.querySelector("input[name='end_date'], #id_end_date");
    const cadenceNouns = {
      daily: "day",
      weekly: "week",
      monthly: "month",
    };
    const cleanRecapValue = (value, fallback) => {
      const next = (value || "").trim().toLowerCase();
      return next || fallback;
    };
    const syncRecap = () => {
      if (recapActivity && activityField) {
        recapActivity.textContent = cleanRecapValue(activityField.value, "sessions");
      }
      if (recapUnit && unitField) {
        recapUnit.textContent = cleanRecapValue(unitField.value, "session");
      }
      if (recapCadence) {
        const selectedCadence = document.querySelector("input[name='cadence']:checked, [data-project-cadence], select[name='cadence'], #id_cadence");
        const cadence = selectedCadence ? selectedCadence.value : "weekly";
        recapCadence.textContent = cadenceNouns[cadence] || "week";
      }
      if (recapDuration) {
        const selectedDuration = document.querySelector("input[name='duration']:checked");
        if (!selectedDuration || selectedDuration.value !== "until") {
          recapDuration.textContent = "for as long as you both keep it up";
        } else if (endDateField && endDateField.value) {
          const date = new Date(endDateField.value);
          if (Number.isNaN(date.getTime())) {
            recapDuration.textContent = "until the date you pick";
          } else {
            recapDuration.textContent = `until ${date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`;
          }
        } else {
          recapDuration.textContent = "until the date you pick";
        }
      }
    };

    [activityField, unitField].forEach((field) => {
      if (!field) {
        return;
      }
      field.addEventListener("input", syncRecap);
      field.addEventListener("change", syncRecap);
    });
    document.querySelectorAll("input[name='cadence'], [data-project-cadence], select[name='cadence'], #id_cadence").forEach((input) => {
      input.addEventListener("change", syncRecap);
    });
    document.querySelectorAll("input[name='duration']").forEach((input) => {
      input.addEventListener("change", syncRecap);
    });
    if (endDateField) {
      endDateField.addEventListener("input", syncRecap);
      endDateField.addEventListener("change", syncRecap);
    }

    document.querySelectorAll("input[type='radio'][data-name][data-activity][data-unit][data-cadence]").forEach((input) => {
      input.addEventListener("change", () => {
        if (input.checked) {
          applyTemplate(input);
        }
      });
    });

    const checkedTemplate = document.querySelector("input[type='radio'][data-name][data-activity][data-unit][data-cadence]:checked");
    if (checkedTemplate) {
      applyTemplate(checkedTemplate);
    }
    syncRecap();

    const reveal = document.querySelector("[data-date-reveal]");
    if (reveal) {
      const updateReveal = () => {
        const selected = document.querySelector("input[name='duration']:checked, input[name='runs_until']:checked, [data-duration-choice]:checked");
        const show = selected && (selected.value === "until" || selected.value === "date" || selected.dataset.showDate === "true");
        reveal.classList.toggle("is-hidden", !show);
      };

      document.querySelectorAll("input[name='duration'], input[name='runs_until'], [data-duration-choice]").forEach((input) => {
        input.addEventListener("change", updateReveal);
      });
      updateReveal();
    }
  }

  function bindSteppers() {
    document.querySelectorAll("[data-stepper]").forEach((root) => {
      const input = root.querySelector("input[type='number']");
      const display = root.querySelector("[data-stepper-value]");
      const minus = root.querySelector("[data-stepper-minus], [data-stepper-dec]");
      const plus = root.querySelector("[data-stepper-plus], [data-stepper-inc]");

      if (!input) {
        return;
      }

      const clamp = (value) => Math.min(99, Math.max(1, Number.parseInt(value, 10) || 1));
      const sync = (value) => {
        const next = String(clamp(value));
        if (input.value !== next) {
          input.value = next;
        }
        if (display) {
          display.textContent = next;
        }
      };

      if (minus) {
        minus.addEventListener("click", () => sync(Number(input.value) - 1));
      }
      if (plus) {
        plus.addEventListener("click", () => sync(Number(input.value) + 1));
      }
      input.addEventListener("change", () => sync(input.value));
      sync(input.value);
    });
  }

  bindLogForms();
  bindReactions();
  bindLiveSync();
  bindCopies();
  bindShare();
  bindNudges();
  bindCreateHelpers();
  bindSteppers();
}());
