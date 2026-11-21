const STORAGE_KEY = "speakeasy.preferences.v1";
const DEFAULTS = Object.freeze({ theme: "light", fontSize: "medium" });
const THEMES = new Set(["light", "dark"]);
const FONT_SIZES = new Set(["small", "medium", "large"]);

export function readPreferences() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    return {
      theme: THEMES.has(stored.theme) ? stored.theme : DEFAULTS.theme,
      fontSize: FONT_SIZES.has(stored.fontSize) ? stored.fontSize : DEFAULTS.fontSize
    };
  } catch {
    return { ...DEFAULTS };
  }
}

export function applyPreferences(preferences) {
  const theme = THEMES.has(preferences.theme) ? preferences.theme : DEFAULTS.theme;
  const fontSize = FONT_SIZES.has(preferences.fontSize) ? preferences.fontSize : DEFAULTS.fontSize;
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.fontSize = fontSize;
  document.documentElement.style.colorScheme = theme;
  return { theme, fontSize };
}

function persistPreferences(preferences) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
  } catch (error) {
    console.warn("Appearance preferences could not be saved in this browser.", error);
  }
}

function updatePressedState(root, preferences) {
  root.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.themeChoice === preferences.theme));
  });
  root.querySelectorAll("[data-font-size-choice]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.fontSizeChoice === preferences.fontSize));
  });
}

export function setupAppearanceSettings(dialog) {
  if (!dialog) return;
  let preferences = applyPreferences(readPreferences());
  updatePressedState(dialog, preferences);

  dialog.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.addEventListener("click", () => {
      preferences = applyPreferences({ ...preferences, theme: button.dataset.themeChoice });
      persistPreferences(preferences);
      updatePressedState(dialog, preferences);
    });
  });

  dialog.querySelectorAll("[data-font-size-choice]").forEach((button) => {
    button.addEventListener("click", () => {
      preferences = applyPreferences({ ...preferences, fontSize: button.dataset.fontSizeChoice });
      persistPreferences(preferences);
      updatePressedState(dialog, preferences);
    });
  });
}
