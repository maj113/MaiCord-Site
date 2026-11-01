// "Copy link": the maicord:// link stays visible and selectable without this script.
(() => {
  const button = document.getElementById("copy"), link = document.getElementById("link"), note = document.getElementById("copied");
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
})();
