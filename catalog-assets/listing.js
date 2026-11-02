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
