// "Copy link", and a hint when nothing opens after "Install in MaiCord". The maicord:// link works without this
// script and stays visible and selectable; the script only adds the button and the hint.
(() => {
  const install = document.getElementById("install"), link = document.getElementById("link"),
    note = document.getElementById("copied"), button = document.getElementById("copy"),
    hint = document.getElementById("hint"), help = document.getElementById("help");
  button.hidden = false;
  button.onclick = async () => {
    try {
      await navigator.clipboard.writeText(link.textContent);
      note.textContent = "Copied";
    } catch {
      getSelection().selectAllChildren(link);
      note.textContent = "Selected: press Ctrl+C";
    }
  };

  // When MaiCord (or the browser's "open this app?" prompt) takes the focus, the page blurs or hides. If
  // nothing like that happens within three seconds of the click, no application answered: say so. The text
  // under the button, which explains it without a script, gives way to the hint.
  let timer;
  const away = () => clearTimeout(timer);
  for (const type of ["blur", "pagehide"]) addEventListener(type, away);
  document.addEventListener("visibilitychange", () => { if (document.hidden) away(); });
  install.onclick = () => {
    hint.hidden = true;
    clearTimeout(timer);
    timer = setTimeout(() => {
      help.hidden = true;
      hint.hidden = false;
    }, 3000);
  };
})();
