const demoModes = {
  structured: {
    prompt: "Tell me about a time you had to solve a difficult problem.",
    guidance: "Describe the situation, the action you took and the result.",
    time: "01:00"
  },
  spontaneous: {
    prompt: "Design systems improve consistency, but do they limit product innovation?",
    guidance: "Choose a side, support it with an example and make your point clearly.",
    time: "01:30"
  }
};

for (const tab of document.querySelectorAll("[data-demo-mode]")) {
  tab.addEventListener("click", () => {
    const mode = demoModes[tab.dataset.demoMode];
    if (!mode) return;
    document.querySelectorAll("[data-demo-mode]").forEach((item) => {
      const selected = item === tab;
      item.classList.toggle("active", selected);
      item.setAttribute("aria-selected", String(selected));
      item.tabIndex = selected ? 0 : -1;
    });
    document.querySelector("#demo-prompt-text").textContent = mode.prompt;
    document.querySelector("#demo-guidance").textContent = mode.guidance;
    document.querySelector("#demo-time").textContent = mode.time;
  });
}
