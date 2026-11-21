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

const demoTabs = [...document.querySelectorAll("[data-demo-mode]")];

function selectDemoMode(tab, moveFocus = false) {
  const mode = demoModes[tab.dataset.demoMode];
  if (!mode) return;
  demoTabs.forEach((item) => {
    const selected = item === tab;
    item.classList.toggle("active", selected);
    item.setAttribute("aria-selected", String(selected));
    item.tabIndex = selected ? 0 : -1;
  });
  document.querySelector("#demo-preview").setAttribute("aria-labelledby", tab.id);
  document.querySelector("#demo-prompt-text").textContent = mode.prompt;
  document.querySelector("#demo-guidance").textContent = mode.guidance;
  document.querySelector("#demo-time").textContent = mode.time;
  if (moveFocus) tab.focus();
}

for (const tab of demoTabs) {
  tab.addEventListener("click", () => selectDemoMode(tab));
  tab.addEventListener("keydown", (event) => {
    const current = demoTabs.indexOf(tab);
    let next = current;
    if (event.key === "ArrowRight") next = (current + 1) % demoTabs.length;
    else if (event.key === "ArrowLeft") next = (current - 1 + demoTabs.length) % demoTabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = demoTabs.length - 1;
    else return;
    event.preventDefault();
    selectDemoMode(demoTabs[next], true);
  });
}
