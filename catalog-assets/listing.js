// Search, filters and sort. Without this script the page lists every item.
(() => {
  const form = document.getElementById("filters"), list = document.getElementById("items"),
    count = document.getElementById("count"), empty = document.getElementById("empty"), why = document.getElementById("why"),
    search = form.elements.q, sort = form.elements.sort, chips = [...form.querySelectorAll(".chip")],
    cards = [...list.children], params = new URLSearchParams(location.search), facets = {};
  search.value = params.get("q") || "";
  if ([...sort.options].some(o => o.value === params.get("sort"))) sort.value = params.get("sort");
  for (const chip of chips)
    if (params.get(chip.dataset.facet) === chip.dataset.value) facets[chip.dataset.facet] = chip.dataset.value;

  const apply = () => {
    const words = search.value.toLowerCase().split(/\s+/).filter(Boolean), key = "sort" + sort.value[0].toUpperCase() + sort.value.slice(1);
    let shown = 0;
    for (const card of cards) {
      const ok = words.every(w => card.dataset.text.includes(w)) &&
        Object.entries(facets).every(([facet, value]) => (card.dataset[facet] || "").split(" ").includes(value));
      card.hidden = !ok;
      shown += ok;
    }
    cards.sort((a, b) => sort.value === "name" ? a.dataset.sortName.localeCompare(b.dataset.sortName) :
      (a.dataset[key] - b.dataset[key]) || a.dataset.sortName.localeCompare(b.dataset.sortName));
    list.append(...cards);
    for (const chip of chips) chip.setAttribute("aria-pressed", facets[chip.dataset.facet] === chip.dataset.value);
    const noun = list.dataset.noun;
    count.textContent = shown === cards.length ? `${shown} ${noun}${shown === 1 ? "" : "s"}` :
      `Showing ${shown} of ${cards.length} ${noun}s`;
    empty.hidden = shown > 0;
    if (!shown) {
      const parts = [];
      if (search.value.trim()) parts.push(`“${search.value.trim()}”`);
      for (const chip of chips) if (chip.getAttribute("aria-pressed") === "true") parts.push(chip.firstChild.textContent);
      why.textContent = `No ${noun}s match ${parts.join(" + ")}. Try fewer words, or clear the filters.`;
    }
    const query = new URLSearchParams();
    if (search.value.trim()) query.set("q", search.value.trim());
    for (const [facet, value] of Object.entries(facets)) query.set(facet, value);
    if (sort.value !== "name") query.set("sort", sort.value);
    history.replaceState(null, "", query.toString() ? "?" + query : location.pathname);
  };
  form.onsubmit = e => e.preventDefault();
  search.oninput = sort.onchange = apply;
  for (const chip of chips)
    chip.onclick = () => {
      if (facets[chip.dataset.facet] === chip.dataset.value) delete facets[chip.dataset.facet];
      else facets[chip.dataset.facet] = chip.dataset.value;
      apply();
    };
  empty.querySelector("button").onclick = () => {
    search.value = "";
    for (const facet of Object.keys(facets)) delete facets[facet];
    apply();
    search.focus();
  };

  // The sort <select> keeps the value and the form; a button and a listbox popup (the select-only combobox pattern)
  // replace it on screen, in the theme's colours. Arrows, Home, End, Enter, Space, Esc, Tab and typing a name work.
  const dropdown = select => {
    const box = select.closest(".sortbox"), label = box.querySelector("label"), wrap = document.createElement("div"),
      button = document.createElement("button"), text = document.createElement("span"), menu = document.createElement("ul"),
      choices = [...select.options], id = select.id;
    let active = 0, typed = "", timer = 0;
    wrap.className = "dd";
    label.id = id + "-label";
    label.htmlFor = button.id = id + "-button";
    text.id = id + "-value";
    Object.assign(button, { type: "button", className: "dd-button" });
    for (const [name, value] of [["role", "combobox"], ["aria-haspopup", "listbox"], ["aria-expanded", "false"],
      ["aria-controls", id + "-list"], ["aria-labelledby", `${label.id} ${text.id}`]]) button.setAttribute(name, value);
    button.append(text);
    button.insertAdjacentHTML("beforeend", '<svg class="dd-chevron" viewBox="0 0 12 12" aria-hidden="true"><path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>');
    Object.assign(menu, { id: id + "-list", className: "dd-list", hidden: true, tabIndex: -1 });
    menu.setAttribute("role", "listbox");
    menu.setAttribute("aria-labelledby", label.id);
    const items = choices.map((choice, n) => {
      const item = document.createElement("li");
      item.id = `${id}-option-${n}`;
      item.setAttribute("role", "option");
      item.textContent = choice.text;
      menu.append(item);
      return item;
    });
    const sync = () => {
      text.textContent = choices[select.selectedIndex].text;
      items.forEach((item, n) => item.setAttribute("aria-selected", n === select.selectedIndex));
    };
    const mark = n => {
      active = n;
      items.forEach((item, i) => item.classList.toggle("active", i === n));
      button.setAttribute("aria-activedescendant", items[n].id);
      items[n].scrollIntoView({ block: "nearest" });
    };
    const show = (n = select.selectedIndex) => {
      menu.hidden = false;
      button.setAttribute("aria-expanded", "true");
      mark(n);
    };
    const hide = () => {
      menu.hidden = true;
      button.setAttribute("aria-expanded", "false");
      button.removeAttribute("aria-activedescendant");
    };
    const choose = n => {
      if (n !== select.selectedIndex) {
        select.selectedIndex = n;
        sync();
        select.dispatchEvent(new Event("change"));
      }
    };
    // Typing a name jumps to the next option that starts with it; the same letter again cycles.
    const find = key => {
      typed += key.toLowerCase();
      clearTimeout(timer);
      timer = setTimeout(() => typed = "", 700);
      const word = typed.split("").every(c => c === typed[0]) ? typed[0] : typed, from = word.length === 1 ? active + 1 : active;
      for (let k = 0; k < choices.length; k++) {
        const n = (from + k) % choices.length;
        if (choices[n].text.toLowerCase().startsWith(word)) return n;
      }
      return -1;
    };
    button.onclick = () => menu.hidden ? show() : hide();
    button.onkeyup = e => { if (e.key === " ") e.preventDefault(); };
    button.onkeydown = e => {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      const isOpen = !menu.hidden, last = choices.length - 1;
      if (e.key.length === 1 && e.key !== " " || (e.key === " " && typed)) {
        const n = find(e.key);
        if (n >= 0) isOpen ? mark(n) : show(n);
        e.preventDefault();
      } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        if (isOpen) mark(Math.min(last, Math.max(0, active + (e.key === "ArrowDown" ? 1 : -1))));
        else show();
        e.preventDefault();
      } else if (e.key === "Home" || e.key === "End") {
        const n = e.key === "Home" ? 0 : last;
        isOpen ? mark(n) : show(n);
        e.preventDefault();
      } else if (e.key === "Enter" || e.key === " ") {
        if (isOpen) { choose(active); hide(); } else show();
        e.preventDefault();
      } else if (e.key === "Escape" && isOpen) {
        hide();
        e.preventDefault();
      } else if (e.key === "Tab" && isOpen) {
        choose(active);
        hide();
      }
    };
    // Clicking keeps the focus on the button; a click or a focus change anywhere else closes the list.
    menu.onmousedown = e => e.preventDefault();
    menu.onmouseover = e => { const n = items.indexOf(e.target.closest("li")); if (n >= 0) mark(n); };
    menu.onclick = e => {
      const n = items.indexOf(e.target.closest("li"));
      if (n < 0) return;
      choose(n);
      hide();
      button.focus();
    };
    document.addEventListener("pointerdown", e => { if (!wrap.contains(e.target)) hide(); });
    wrap.onfocusout = e => { if (!wrap.contains(e.relatedTarget)) hide(); };
    sync();
    wrap.append(button, menu);
    select.after(wrap);
    select.hidden = true;
    box.classList.add("enhanced");
  };
  dropdown(sort);

  // Each row of chips is one tab stop (the pressed chip, else the first); the arrow keys, Home and End move inside it.
  for (const row of form.querySelectorAll("[role=toolbar]")) {
    const own = [...row.querySelectorAll(".chip")], stop = chip => own.forEach(c => c.tabIndex = c === chip ? 0 : -1);
    stop(own.find(c => c.dataset.value === facets[c.dataset.facet]) || own[0]);
    row.onfocusin = e => { if (own.includes(e.target)) stop(e.target); };
    row.onkeydown = e => {
      const steps = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }, at = own.indexOf(document.activeElement);
      if (at < 0 || e.altKey || e.ctrlKey || e.metaKey) return;
      let to;
      if (e.key in steps) to = (at + steps[e.key] + own.length) % own.length;
      else if (e.key === "Home") to = 0;
      else if (e.key === "End") to = own.length - 1;
      else return;
      e.preventDefault();
      own[to].focus();
    };
  }
  form.hidden = count.hidden = false;
  apply();
})();
