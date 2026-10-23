/* Optional Colossal Cave UI. It never reads case state or VolShell output. */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  let adapter = null, active = false, openedDialog = false, previousMode = "output";
  let previousFocus = null, previousScroll = 0, outputScroll = 0, shellScroll = 0;
  let sessionId = null, poll = null, sequence = 0, busy = false, closing = null, starting = null;
  let outputButtonDisabled = false, shellButtonDisabled = false;

  function status(message) {
    $("adventureStatus").textContent = message;
  }
  function showMenu(message = "") {
    $("adventureMenu").hidden = false;
    $("adventureOutput").hidden = true;
    $("adventureForm").hidden = true;
    $("adventureExit").textContent = "Return to console";
    status(message || "Choose an edition.");
    $("adventure1977").focus({preventScroll:true});
  }
  function render(snapshot) {
    if (!active || snapshot.session_id !== sessionId) return;
    const output = $("adventureOutput");
    const follows = output.scrollHeight - output.scrollTop - output.clientHeight < 24;
    if (output.textContent !== snapshot.output) {
      output.textContent = snapshot.output;
      output.scrollTop = follows ? output.scrollHeight : Math.min(output.scrollTop, output.scrollHeight);
    }
    $("adventureForm").hidden = snapshot.status !== "running";
    $("adventureExit").textContent = snapshot.status === "running" ? "Save and return" : "Return to console";
    const label = snapshot.edition === "1977" ? "1977 edition · 350 points" : "1995 edition · 430 points";
    status(snapshot.error || (snapshot.status === "running" ? label : "Game ended. Your saved progress remains available."));
  }
  async function refresh(id) {
    try {
      const snapshot = await adapter.api("adventure/status");
      if (active && id === sequence && sessionId === snapshot.session_id) render(snapshot);
    } catch (e) {
      if (active && id === sequence) status("Game connection failed: " + e.message);
    }
  }
  async function start(edition, fresh = false) {
    if (!["1977", "1995"].includes(edition)) throw Error("Unknown Adventure edition");
    if (busy) return;
    busy = true;
    const launchSequence = sequence;
    const operation = (async () => {
      status("Starting Adventure…");
      try {
        const snapshot = await adapter.api("adventure/start", {edition, new:fresh});
        if (!active || launchSequence !== sequence) {
          await adapter.api("adventure/close", {session_id:snapshot.session_id});
          return;
        }
        sessionId = snapshot.session_id;
        $("adventureMenu").hidden = true;
        $("adventureOutput").hidden = false;
        $("adventureForm").hidden = false;
        render(snapshot);
        $("adventureInput").focus({preventScroll:true});
        const id = ++sequence;
        clearInterval(poll);
        poll = setInterval(() => refresh(id), 250);
      } catch (e) {
        if (active && launchSequence === sequence) showMenu(e.message);
      }
    })();
    starting = operation;
    try { await operation; }
    finally {
      if (starting === operation) starting = null;
      busy = false;
    }
  }
  async function exit() {
    if (!active) return;
    active = false;
    ++sequence;
    clearInterval(poll);
    poll = null;
    const leaving = sessionId;
    sessionId = null;
    $("adventurePanel").hidden = true;
    $("adventureDevButton").setAttribute("aria-pressed", "false");
    $("consoleOutputMode").disabled = outputButtonDisabled;
    $("consoleVolshellMode").disabled = shellButtonDisabled;
    window.WorkbenchVolshell.restoreMode(previousMode);
    $("liveConsole").scrollTop = outputScroll;
    $("volshellOutput").scrollTop = shellScroll;
    if (openedDialog && $("consoleZoom").open) $("consoleZoom").close();
    else if (previousFocus?.isConnected) previousFocus.focus({preventScroll:true});
    window.scrollTo({top:previousScroll, behavior:"instant"});
    if (leaving) {
      closing = adapter.api("adventure/close", {session_id:leaving})
        .catch(e => console.error("Adventure cleanup failed", e));
      await closing;
      closing = null;
    }
  }
  async function launch({edition = "select"} = {}) {
    if (!["select", "1977", "1995"].includes(edition)) throw Error("Unknown Adventure edition");
    if (!adapter) throw Error("Adventure is not ready");
    if (closing) await closing;
    if (starting) await starting;
    if (active) {
      if (edition !== "select" && !sessionId) await start(edition);
      else $("adventurePanel").focus({preventScroll:true});
      return;
    }
    previousMode = $("consoleZoom").open ? window.WorkbenchVolshell.currentMode() : "output";
    previousFocus = document.activeElement;
    previousScroll = window.scrollY;
    outputScroll = $("liveConsole").scrollTop;
    shellScroll = $("volshellOutput").scrollTop;
    outputButtonDisabled = $("consoleOutputMode").disabled;
    shellButtonDisabled = $("consoleVolshellMode").disabled;
    openedDialog = !$("consoleZoom").open;
    active = true;
    if (openedDialog) adapter.openMonitor();
    $("consoleOutputMode").disabled = true;
    $("consoleVolshellMode").disabled = true;
    window.WorkbenchVolshell.enterAdventure();
    $("adventurePanel").hidden = false;
    $("adventureDevButton").setAttribute("aria-pressed", "true");
    if (edition === "select") showMenu();
    else await start(edition);
  }
  function mount(options) {
    adapter = options;
    configure();
    $("adventure1995").onclick = () => start("1995");
    $("adventureNew1995").onclick = () => start("1995", true);
    $("adventure1977").onclick = () => start("1977");
    $("adventureNew1977").onclick = () => start("1977", true);
    $("adventureExit").onclick = () => exit();
    $("adventureForm").onsubmit = async event => {
      event.preventDefault();
      if (busy || !sessionId) return;
      const command = $("adventureInput").value.trim();
      if (!command) return;
      busy = true;
      $("adventureSend").disabled = true;
      try {
        const snapshot = await adapter.api("adventure/input", {session_id:sessionId, command});
        $("adventureInput").value = "";
        render(snapshot);
        $("adventureInput").focus({preventScroll:true});
      } catch (e) { status(e.message); }
      finally { busy = false; $("adventureSend").disabled = false; }
    };
    $("adventureInput").addEventListener("keydown", event => {
      if (event.key === "Escape") { event.preventDefault(); $("adventureExit").focus(); }
    });
    $("adventureDevButton").onclick = () => launch({edition:"select"});
    for (const [id, edition] of [["fieldAdventure1977", "1977"], ["fieldAdventure1995", "1995"]]) {
      const activate = event => {
        if (event.type === "click" && event.detail !== 0) return;
        if (document.documentElement.dataset.theme !== "fallout-76-field-terminal" || !$("consoleZoom").open) return;
        event.preventDefault();
        void launch({edition}).catch(error => status(error.message));
      };
      $(id).ondblclick = activate;
      $(id).onclick = activate;
    }
    window.addEventListener("pagehide", () => {
      if (sessionId) navigator.sendBeacon?.("/api/adventure/close", new Blob(
        [JSON.stringify({session_id:sessionId})], {type:"application/json"}));
    });
  }
  async function configure() {
    $("adventureDevButton").hidden = !(location.hostname === "localhost" &&
      new URLSearchParams(location.search).has("adventure-dev"));
  }
  window.Adventure = Object.freeze({launch, mount, configure, exit,
    closed: () => { if (active) void exit(); },
    isActive: () => active,
  });
})();
