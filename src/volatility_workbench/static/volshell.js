/* Case-bound interactive UI. The backend owns sessions, execution and connection
 * readiness. Output and AI proposals are always plain text, never HTML. */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const active = session => !!session && ["starting", "running", "stopping"].includes(session.status);
  let adapter, snapshot = {session:null, busy:false}, cases = [], targetCase = null, investigationBusy = false;
  let monitorMode = "output", interactionMode = "manual", lastSelected, caseKey = "", imageKey = "", pending = false;
  let completion = "", dismissedCompletion = "", suggestionRequest = 0, suggesting = false, proposal = null;
  const drafts = new Map(), choices = new Map();
  const session = () => snapshot.session;
  const bound = () => active(session()) && session().case_id === targetCase;
  const ready = () => bound() && session().status === "running" && session().ready === true && !investigationBusy && !agentActive();
  const caseName = id => cases.find(item => item.id === id)?.title || id || "No case selected";
  const binding = () => ({case_id:session().case_id, session_id:session().id});
  const bindingKey = () => active(session()) ? JSON.stringify([targetCase, session().case_id, session().id]) : "";
  let shownBinding = "", notifiedApprovalKey = "";
  let polledSnapshot = snapshot, eventSource = null, streamCase = null, streamSnapshot = null, streamValid = false, streamFrame = 0;
  let streamRetry = null, streamRetryAttempt = 0;
  const seenActivities = new Set();
  const agentActivity = () => snapshot.agent_activity?.case_id === targetCase ? snapshot.agent_activity : null;
  const agentActive = () => ["starting", "running"].includes(agentActivity()?.status);

  function effectiveSnapshot() {
    if (!streamValid || streamSnapshot?.case_id !== targetCase) return polledSnapshot;
    // Polling still owns investigation summaries and safe metadata needed to
    // disconnect an interactive session bound to a different case. Streamed
    // output always belongs to this exact case and wins over an older poll.
    const other = active(polledSnapshot.session) && polledSnapshot.session.case_id !== targetCase ? polledSnapshot.session : null;
    return {...polledSnapshot, ...streamSnapshot,
      session:streamSnapshot.session || (streamSnapshot.busy && other ? {...other, entries:[]} : null)};
  }
  function closeStream() {
    eventSource?.close();
    eventSource = null; streamCase = null; streamSnapshot = null; streamValid = false;
    if (streamFrame) cancelAnimationFrame(streamFrame);
    streamFrame = 0;
    if (streamRetry !== null) clearTimeout(streamRetry);
    streamRetry = null; streamRetryAttempt = 0;
  }
  function syncStream() {
    if (!$("consoleZoom").open || !targetCase || typeof EventSource !== "function") { closeStream(); return; }
    if (eventSource && streamCase === targetCase) return;
    closeStream();
    connectStream(targetCase);
  }
  function connectStream(requestedCase) {
    const source = new EventSource("/api/volshell/events?case=" + encodeURIComponent(requestedCase));
    eventSource = source; streamCase = requestedCase;
    source.addEventListener("volshell", event => {
      if (source !== eventSource || targetCase !== requestedCase || !$("consoleZoom").open) return;
      let value;
      try { value = JSON.parse(event.data); } catch { return; }
      if (!value || value.case_id !== requestedCase ||
          value.session && value.session.case_id !== requestedCase ||
          value.agent_activity && value.agent_activity.case_id !== requestedCase) return;
      streamSnapshot = value; streamValid = true;
      streamRetryAttempt = 0;
      if (streamRetry !== null) clearTimeout(streamRetry);
      streamRetry = null;
      if (!streamFrame) streamFrame = requestAnimationFrame(() => {
        streamFrame = 0;
        if (source !== eventSource || targetCase !== requestedCase) return;
        snapshot = effectiveSnapshot();
        render();
      });
    });
    source.onerror = () => {
      if (source !== eventSource) return;
      streamValid = false;
      // CONNECTING keeps the browser's native retry. Non-200 responses can
      // instead close it permanently; retry those with a capped backoff while
      // polling remains the fallback. A case change or collapse cancels this.
      if (source.readyState === EventSource.CLOSED && streamRetry === null) {
        source.close();
        const delay = Math.min(1000 * 2 ** Math.min(streamRetryAttempt++, 4), 15000);
        streamRetry = setTimeout(() => {
          streamRetry = null;
          if (source !== eventSource || targetCase !== requestedCase || !$("consoleZoom").open) return;
          source.close();
          connectStream(requestedCase);
        }, delay);
      }
    };
  }
  function showAgentActivity() {
    const activity = agentActivity();
    if (!activity) return;
    const key = JSON.stringify([activity.case_id, activity.job_id, activity.id]);
    if (!agentActive() || seenActivities.has(key)) return;
    seenActivities.add(key);
    if (seenActivities.size > 32) seenActivities.delete(seenActivities.values().next().value);
    if ($("consoleZoom").open && (monitorMode !== "output" || adapter.consoleCase() === targetCase)) monitorMode = "agent";
  }

  function showError(value) {
    $("volshellError").textContent = value?.message || String(value || "");
    $("volshellError").hidden = !$("volshellError").textContent;
  }
  function forgetProposal() {
    ++suggestionRequest;
    suggesting = false;
    proposal = null;
    $("volshellProposal").hidden = true;
    $("volshellProposalCommand").textContent = "";
    $("volshellProposalExplanation").textContent = "";
    $("volshellAIStatus").textContent = "";
  }
  function chooseCase(id) {
    if (targetCase === (id || null)) { render(); return; }
    if (targetCase) drafts.set(targetCase, $("volshellInput").value);
    targetCase = id || null;
    $("volshellInput").value = drafts.get(targetCase) || "";
    imageKey = "";
    forgetProposal();
    interactionMode = "manual";
    showError("");
    render();
  }
  function setMode(value, focus = false) {
    monitorMode = value;
    const shell = value !== "output", agent = value === "agent";
    $("expandedConsoleHost").hidden = shell;
    $("volshellPanel").hidden = value !== "volshell";
    $("volshellAgentPanel").hidden = !agent;
    $("consoleVolshellMode").setAttribute("aria-pressed", String(shell));
    $("consoleOutputMode").setAttribute("aria-pressed", String(!shell));
    $("consoleZoom").setAttribute("aria-labelledby", agent ? "volshellAgentTitle" : shell ? "volshellTitle" : adapter?.hasConsole() ? "liveConsoleTitle" : "emptyConsoleTitle");
    if (focus && $("consoleZoom").open) {
      const input = interactionMode === "suggestions" ? $("volshellAIInput") : interactionMode === "investigation" ? $("volshellInvestigationInput") : $("volshellInput");
      (agent ? $("volshellAgentOutput") : shell ? ready() ? input : $("volshellCase") : adapter.hasConsole() ? $("expandConsole") : $("collapseEmptyConsole")).focus({preventScroll:true});
    }
  }
  function populateTargets() {
    const nextCaseKey = JSON.stringify(cases.map(item => [item.id, item.title]));
    if (caseKey !== nextCaseKey) {
      $("volshellCase").replaceChildren(...cases.map(item => new Option(item.title, item.id)));
      caseKey = nextCaseKey;
    }
    $("volshellCase").value = targetCase || "";
    const images = cases.find(item => item.id === targetCase)?.images || [];
    const nextImageKey = JSON.stringify([targetCase, images.map(item => [item.id, item.path, item.discovery?.detected_os])]);
    if (imageKey !== nextImageKey) {
      const remembered = choices.get(targetCase);
      $("volshellImage").replaceChildren(new Option(images.length ? "Choose a capture…" : "No registered captures", ""),
        ...images.map(item => new Option(item.id + " · " + item.path, item.id)));
      $("volshellImage").value = images.some(item => item.id === remembered?.image) ? remembered.image : images.length === 1 ? images[0].id : "";
      const known = images.find(item => item.id === $("volshellImage").value)?.discovery?.detected_os;
      const os = String(known || "").toLowerCase();
      $("volshellMode").value = remembered?.mode || (["windows", "linux", "mac"].includes(os) ? os : ["darwin", "macos"].includes(os) ? "mac" : "generic");
      imageKey = nextImageKey;
    }
    if (bound()) {
      $("volshellImage").value = session().image_id;
      $("volshellMode").value = session().mode;
    }
    $("volshellCase").disabled = !cases.length || pending;
    $("volshellImage").disabled = active(session()) || pending || !images.length;
    $("volshellMode").disabled = active(session()) || pending;
  }
  function starterCommands() {
    const mode = bound() ? session().mode : $("volshellMode").value;
    const common = ["hh()", "help()", "db(0x0)", "dw(0x0)", "dd(0x0)", "dq(0x0)", "self.current_layer", "list(context.layers)"];
    if (mode === "windows") return ["hh()", "ps()", "help(ps)", "cp(4)", 'dt("_EPROCESS")', ...common.slice(1)];
    if (mode === "linux") return ["hh()", "ps()", "help(ps)", "cp(1)", 'dt("task_struct")', ...common.slice(1)];
    if (mode === "mac") return ["hh()", "ps()", "help(ps)", "cp(1)", 'dt("proc")', ...common.slice(1)];
    return common;
  }
  function syncGhost() {
    const input = $("volshellInput"), value = input.value;
    const atEnd = input.selectionStart === value.length && input.selectionEnd === value.length;
    const next = !input.disabled && atEnd && !value.includes("\n") && value && value !== dismissedCompletion
      ? starterCommands().find(command => command.startsWith(value) && command !== value) || "" : "";
    completion = next;
    $("volshellGhostPrefix").textContent = next ? value : "";
    $("volshellGhostSuffix").textContent = next ? next.slice(value.length) : "";
    $("volshellSuggestion").textContent = next ? "Suggestion: " + next + ". Tab accepts; Escape dismisses." : "";
    $("volshellAccept").hidden = !next;
    $("volshellGhost").scrollTop = input.scrollTop;
    $("volshellGhost").scrollLeft = input.scrollLeft;
  }
  function acceptCompletion() {
    syncGhost();
    if (!completion || $("volshellInput").disabled) return false;
    $("volshellInput").value = completion;
    $("volshellInput").setSelectionRange(completion.length, completion.length);
    drafts.set(targetCase, completion);
    dismissedCompletion = "";
    syncGhost();
    $("volshellRun").disabled = !ready() || pending;
    return true;
  }
  function renderOutput() {
    const pre = $("volshellOutput"), current = session();
    const output = (current?.entries || []).map(entry => entry.kind === "output" ? entry.text : entry.text + "\n").join("");
    const text = current && current.case_id === targetCase ? (current.earlier_entries ? "[Earlier output is retained in the private session transcript.]\n" : "") + (output || (active(current) ? "Waiting for VolShell output…" : "No output was recorded."))
      : active(current) ? "An interactive session belongs to " + caseName(current.case_id) + ". Select that case to view its output and enter commands, or disconnect it."
        : "Choose a registered capture and connect to VolShell.";
    if (pre.textContent !== text) {
      const follow = pre.scrollHeight - pre.scrollTop - pre.clientHeight < 24;
      const top = pre.scrollTop;
      pre.textContent = text;
      pre.scrollTop = follow ? pre.scrollHeight : top;
    }
  }
  function renderAgent() {
    const activity = agentActivity();
    $("volshellShowAgent").hidden = !activity;
    $("volshellAgentTitle").textContent = "AI VolShell activity · " + caseName(targetCase);
    $("volshellAgentStatus").textContent = activity ? activity.status + " · " + activity.image_id + (activity.error ? " · " + activity.error : "") : "No AI VolShell activity in this case.";
    $("volshellAgentCommand").textContent = activity?.command || "";
    $("volshellAgentCommand").hidden = !activity?.command;
    const text = activity ? (activity.truncated ? "[Showing the latest output; the full observation transcript is retained.]\n" : "") +
      (activity.entries || []).map(entry => entry.kind === "output" ? entry.text : entry.text + "\n").join("") : "";
    const pre = $("volshellAgentOutput");
    if (pre.textContent !== text) {
      const follow = pre.scrollHeight - pre.scrollTop - pre.clientHeight < 24, top = pre.scrollTop;
      pre.textContent = text;
      pre.scrollTop = follow ? pre.scrollHeight : top;
    }
  }
  function renderInvestigation() {
    const record = snapshot.investigation;
    const job = record?.job;
    const matching = job && job.case_id === targetCase && job.volshell_session_id === session()?.id;
    $("volshellInvestigationStatus").textContent = matching ? adapter.formatOperation(job) || "AI investigation · " + job.status : "No AI investigation requested in this session.";
    $("volshellStopAI").hidden = !matching || !["queued", "running", "stopping"].includes(job.status);
    $("volshellStopAI").disabled = pending;
    $("volshellInvestigate").disabled = pending || suggesting || !ready();
    const text = matching ? (record.console?.entries || []).map(entry => "[" + adapter.formatTime(entry.time) + "]\n" + entry.text).join("\n\n") : "";
    const pre = $("volshellInvestigationOutput");
    if (pre.textContent !== text) {
      const follow = pre.scrollHeight - pre.scrollTop - pre.clientHeight < 24, top = pre.scrollTop;
      pre.textContent = text;
      pre.scrollTop = follow ? pre.scrollHeight : top;
    }
    $("volshellInvestigationMessages").textContent = matching ? (record.messages || []).map(message => String(message.role).toUpperCase() + "\n" + message.text).join("\n\n") : "";
  }
  function render() {
    if (!adapter) return;
    syncStream();
    snapshot = effectiveSnapshot();
    showAgentActivity();
    populateTargets();
    const current = session(), connected = active(current), same = bound();
    const key = bindingKey();
    if (key !== shownBinding) { shownBinding = key; forgetProposal(); showError(""); }
    const led = agentActive() || current?.status === "running" && current.ready === true ? "ready" : connected ? "pending" : "off";
    $("volshellLED").dataset.state = led;
    $("volshellLEDLabel").textContent = " · " + (agentActive() ? "AI active in " + caseName(targetCase) : led === "ready" ? "connected to " + caseName(current.case_id) : connected ? current.status === "running" ? "busy" : current.status : "disconnected");
    $("volshellTitle").textContent = "VolShell · " + caseName(targetCase);
    $("volshellBinding").textContent = current && current.case_id === targetCase
      ? "Session bound to " + caseName(current.case_id) + " · " + current.image_id + " · " + current.mode + ". Choose Manual commands, AI command suggestions or AI investigation."
      : connected ? "Active session: " + caseName(current.case_id) + " · " + current.image_id + ". Disconnect it before connecting a different capture."
        : "Interactive commands use the selected original capture. Previous reports and investigation output remain separate.";
    $("volshellBinding").textContent += " VolShell runs Python locally with your account permissions.";
    $("volshellStatus").textContent = pending ? "Request in progress…" : current?.status === "failed" && current.case_id === targetCase ? "Connection failed"
      : connected ? !same ? "Connected to another case" : investigationBusy || agentActive() ? "AI investigation active · manual input paused" : current.status === "starting" ? "Connecting…" : current.status === "stopping" ? "Disconnecting…" : current.ready ? current.continuation ? "Connected · finish the continued block" : "Connected · ready" : "Connected · command running"
        : investigationBusy || agentActive() ? "An investigation is active. Connect when it finishes." : "Disconnected";
    if (current?.case_id === targetCase && current.error && !$("volshellError").textContent) showError(current.error);
    $("volshellConnect").disabled = pending || connected || snapshot.busy || investigationBusy || agentActive() || !targetCase || !$("volshellImage").value;
    $("volshellDisconnect").disabled = pending || !connected || investigationBusy || agentActive();
    $("volshellDisconnect").textContent = connected && !same ? "Disconnect " + caseName(current.case_id) : "Disconnect";
    $("volshellInterrupt").disabled = pending || !same || current?.status !== "running" || investigationBusy || agentActive() || (current.ready && !current.continuation);
    $("volshellInput").disabled = pending || !ready();
    $("volshellRun").disabled = pending || !ready() || (!$("volshellInput").value.trim() && !current?.continuation);
    $("volshellRun").textContent = current?.continuation && !$("volshellInput").value.trim() ? "Finish block" : "Run command";
    $("volshellAISubmit").disabled = suggesting || pending || !ready();
    $("volshellUseProposal").disabled = !ready() || !proposal || proposal.binding !== key;
    renderOutput();
    renderAgent();
    $("volshellInteractionMode").value = interactionMode;
    $("volshellForm").hidden = interactionMode !== "manual";
    $("volshellAI").hidden = interactionMode !== "suggestions";
    $("volshellInvestigation").hidden = interactionMode !== "investigation";
    $("volshellOutput").hidden = interactionMode === "investigation";
    renderInvestigation();
    syncGhost();
    setMode(monitorMode);
  }
  async function perform(path, payload, globalRoute = false) {
    if (pending) return;
    pending = true;
    showError("");
    render();
    try {
      const result = await adapter.api(globalRoute ? path : "volshell/" + path, payload);
      if (result && Object.hasOwn(result, "session")) { polledSnapshot = result; snapshot = effectiveSnapshot(); }
      await adapter.refresh();
      return true;
    } catch (error) { showError(error); return false; }
    finally { pending = false; render(); }
  }
  function rememberChoice() {
    choices.set(targetCase, {image:$("volshellImage").value, mode:$("volshellMode").value});
    render();
  }
  function mount(options) {
    adapter = options;
    window.addEventListener("pagehide", closeStream);
    $("consoleVolshellMode").onclick = () => setMode(agentActive() ? "agent" : "volshell", true);
    $("consoleOutputMode").onclick = () => { chooseCase(adapter.consoleCase()); setMode("output", true); };
    $("volshellInteractiveMode").onclick = () => setMode("volshell", true);
    $("volshellShowAgent").onclick = () => setMode("agent", true);
    $("collapseVolshellAgent").onclick = () => $("consoleZoom").close();
    $("collapseVolshell").onclick = $("collapseEmptyConsole").onclick = () => $("consoleZoom").close();
    $("volshellCase").onchange = () => chooseCase($("volshellCase").value);
    $("volshellImage").onchange = () => {
      const image = cases.find(item => item.id === targetCase)?.images.find(item => item.id === $("volshellImage").value);
      const os = String(image?.discovery?.detected_os || "").toLowerCase();
      $("volshellMode").value = ["windows", "linux", "mac"].includes(os) ? os : ["macos", "darwin"].includes(os) ? "mac" : "generic";
      rememberChoice();
    };
    $("volshellMode").onchange = rememberChoice;
    $("volshellConnect").onclick = () => {
      if ($("volshellConnect").disabled) return;
      rememberChoice();
      perform("start", {case_id:targetCase, image_id:$("volshellImage").value, mode:$("volshellMode").value});
    };
    $("volshellDisconnect").onclick = () => { if (!$("volshellDisconnect").disabled) perform("close", binding()); };
    $("volshellInterrupt").onclick = () => { if (!$("volshellInterrupt").disabled) perform("interrupt", binding()); };
    $("volshellForm").onsubmit = async event => {
      event.preventDefault();
      if ($("volshellRun").disabled) return;
      const text = $("volshellInput").value, key = bindingKey(), selectedCase = targetCase;
      if (await perform("input", {...binding(), text})) {
        if (bindingKey() === key && $("volshellInput").value === text) $("volshellInput").value = "";
        drafts.set(selectedCase, "");
        render();
      }
    };
    $("volshellInput").oninput = () => { dismissedCompletion = ""; drafts.set(targetCase, $("volshellInput").value); render(); };
    $("volshellInput").addEventListener("click", syncGhost);
    $("volshellInput").addEventListener("keyup", syncGhost);
    $("volshellInput").addEventListener("scroll", syncGhost);
    $("volshellInput").addEventListener("keydown", event => {
      if (event.isComposing) return;
      if (event.key === "Tab" && !event.shiftKey && !event.ctrlKey && !event.metaKey && !event.altKey && completion) {
        event.preventDefault(); event.stopPropagation(); acceptCompletion();
      } else if (event.key === "Escape" && completion) {
        event.preventDefault(); event.stopPropagation(); dismissedCompletion = $("volshellInput").value; syncGhost();
      } else if (event.key === "Enter" && !event.shiftKey && !event.repeat) {
        event.preventDefault(); event.stopPropagation(); $("volshellForm").requestSubmit();
      }
    });
    $("volshellAccept").onclick = () => { acceptCompletion(); $("volshellInput").focus(); };
    $("volshellInteractionMode").onchange = () => {
      interactionMode = $("volshellInteractionMode").value;
      render();
    };
    $("volshellAIForm").onsubmit = async event => {
      event.preventDefault();
      const text = $("volshellAIInput").value.trim();
      if (!text || $("volshellAISubmit").disabled) return;
      const key = bindingKey(), request = ++suggestionRequest, target = binding();
      suggesting = true; proposal = null; $("volshellProposal").hidden = true;
      $("volshellAIStatus").textContent = "Preparing a command proposal…";
      render();
      try {
        const result = await adapter.api("volshell/suggest", {...target, text});
        if (request !== suggestionRequest || key !== bindingKey() || !active(session())) return;
        const suggestion = result.suggestion || result;
        if (suggestion.case_id !== target.case_id || suggestion.session_id !== target.session_id) throw Error("The AI response belongs to a different session. Nothing was executed.");
        if (typeof suggestion.command !== "string") throw Error("The AI returned an invalid command proposal. Nothing was executed.");
        proposal = suggestion.command.trim() ? {command:suggestion.command, binding:key} : null;
        $("volshellProposalCommand").textContent = suggestion.command;
        $("volshellProposalCommand").hidden = !proposal;
        $("volshellProposalExplanation").textContent = String(suggestion.explanation || "");
        $("volshellProposal").hidden = false;
        $("volshellAIStatus").textContent = proposal ? "Proposal ready. Review it before using the draft." : "AI response ready. No command was proposed.";
      } catch (error) {
        if (request === suggestionRequest && key === bindingKey()) $("volshellAIStatus").textContent = error.message;
      } finally {
        if (request === suggestionRequest) { suggesting = false; render(); }
      }
    };
    $("volshellUseProposal").onclick = () => {
      if (!proposal || proposal.binding !== bindingKey() || !ready()) return;
      $("volshellInput").value = proposal.command;
      drafts.set(targetCase, proposal.command);
      interactionMode = "manual";
      render();
      $("volshellInput").focus();
      $("volshellInput").setSelectionRange(proposal.command.length, proposal.command.length);
      render();
    };
    $("volshellInvestigationForm").onsubmit = async event => {
      event.preventDefault();
      const text = $("volshellInvestigationInput").value.trim();
      if (!text || $("volshellInvestigate").disabled) return;
      const key = bindingKey();
      if (await perform("investigate", {...binding(), text, request_id:crypto.randomUUID()})) {
        if (bindingKey() === key && $("volshellInvestigationInput").value.trim() === text) $("volshellInvestigationInput").value = "";
      }
    };
    $("volshellStopAI").onclick = () => { if (!$("volshellStopAI").disabled) perform("stop", {}, true); };
  }
  function update(state, selected) {
    cases = state.cases || [];
    investigationBusy = (state.jobs || []).some(job => ["queued", "running", "stopping"].includes(job.status));
    polledSnapshot = state.volshell || {session:null, busy:false};
    snapshot = effectiveSnapshot();
    if (selected !== lastSelected || !cases.some(item => item.id === targetCase)) {
      lastSelected = selected;
      chooseCase(selected);
    } else render();
    const approvalCase = session()?.case_id || targetCase;
    const approvalKey = (state.approvals || []).filter(item => item.case_id === approvalCase).map(item => item.id).sort().join("|");
    if (!approvalKey) { $("volshellApprovalNotice").hidden = true; notifiedApprovalKey = ""; }
    if ($("consoleZoom").open && approvalKey && approvalKey !== notifiedApprovalKey) {
      notifiedApprovalKey = approvalKey;
      $("consoleZoom").close();
      queueMicrotask(() => adapter.showApprovals(approvalCase));
    }
  }
  window.WorkbenchVolshell = Object.freeze({mount, update,
    isShellMode: () => monitorMode !== "output",
    hasActiveSession: () => active(session()),
    showOutput: () => { chooseCase(adapter.consoleCase()); setMode("output"); },
    opened: () => { if (monitorMode === "output") chooseCase(adapter.consoleCase()); render(); },
    closed: () => { closeStream(); snapshot = polledSnapshot; setMode("output"); },
    open: caseId => { chooseCase(caseId); const mode = agentActive() ? "agent" : "volshell"; setMode(mode); adapter.openMonitor(); setMode(mode, true); },
  });
})();
