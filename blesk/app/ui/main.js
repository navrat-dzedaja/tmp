// Blesk UI — vanilla JS, no framework. Talks to the Rust core via Tauri IPC.
const { invoke } = window.__TAURI__.core;

const $ = (id) => document.getElementById(id);
const statusEl = $("status");
const listEl = $("channel-list");
const searchEl = $("search");
const groupEl = $("group-filter");

let items = [];
let selected = null;

$("load-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = $("playlist-url").value.trim();
  const button = $("load-btn");
  button.disabled = true;
  statusEl.textContent = "Stahuji playlist…";
  try {
    const text = await invoke("fetch_text", { url });
    statusEl.textContent = "Parsuji…";
    const playlist = await invoke("parse_m3u", { text });
    items = playlist.items;
    fillGroups(items);
    searchEl.disabled = groupEl.disabled = false;
    render();
  } catch (error) {
    statusEl.textContent = `Chyba: ${error}`;
    items = [];
    listEl.replaceChildren();
  } finally {
    button.disabled = false;
  }
});

searchEl.addEventListener("input", render);
groupEl.addEventListener("change", render);

function fillGroups(items) {
  const groups = [...new Set(items.map((i) => i.group).filter(Boolean))].sort();
  groupEl.replaceChildren(new Option("Všechny skupiny", ""));
  for (const group of groups) groupEl.append(new Option(group, group));
}

function render() {
  const query = searchEl.value.trim().toLowerCase();
  const group = groupEl.value;
  const visible = items.filter(
    (item) =>
      (!group || item.group === group) &&
      (!query || item.name.toLowerCase().includes(query)),
  );
  statusEl.textContent = `${visible.length} / ${items.length} položek`;

  // Cap DOM size until the list is virtualized.
  const fragment = document.createDocumentFragment();
  for (const item of visible.slice(0, 500)) {
    const li = document.createElement("li");
    if (item === selected) li.classList.add("active");
    const logo = item.attrs["tvg-logo"];
    if (logo) {
      const img = document.createElement("img");
      img.src = logo;
      img.loading = "lazy";
      img.onerror = () => img.remove();
      li.append(img);
    }
    const span = document.createElement("span");
    span.textContent = item.name;
    li.append(span);
    if (item.group) {
      const groupSpan = document.createElement("span");
      groupSpan.className = "group";
      groupSpan.textContent = item.group;
      li.append(groupSpan);
    }
    li.addEventListener("click", () => select(item, li));
    fragment.append(li);
  }
  listEl.replaceChildren(fragment);
}

function select(item, li) {
  selected = item;
  listEl.querySelector(".active")?.classList.remove("active");
  li.classList.add("active");
  $("detail").hidden = false;
  $("detail-name").textContent = item.name;
  $("detail-group").textContent = item.group ?? "";
  $("detail-url").textContent = item.url;
  const player = $("player");
  player.hidden = true;
  player.pause();
  player.removeAttribute("src");
}

$("copy-url").addEventListener("click", () => {
  if (selected) navigator.clipboard.writeText(selected.url);
});

$("try-play").addEventListener("click", () => {
  if (!selected) return;
  const player = $("player");
  player.hidden = false;
  player.src = selected.url;
  player.play().catch(() => {
    statusEl.textContent = "Formát webview nepřehraje — čeká na libmpv integraci.";
  });
});
