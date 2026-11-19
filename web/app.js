const cobolEditor = document.querySelector("#cobol-source");
const pythonEditor = document.querySelector("#python-output");
const programInput = document.querySelector("#program-input");
const programOutput = document.querySelector("#program-output");
const notice = document.querySelector("#notice");
const sourceGutter = document.querySelector("#source-gutter");
const pythonGutter = document.querySelector("#python-gutter");
const sourceCount = document.querySelector("#source-count");
const pythonStatus = document.querySelector("#python-status");
const runStatus = document.querySelector("#run-status");
const convertButton = document.querySelector("#convert");
const runButton = document.querySelector("#run-python");
const copyButton = document.querySelector("#copy-python");
const sampleInputs = "C12345\nTest User\nM\n20000101\n1234567890\nL12345\n10000\n12\n12";

function updateEditorMeta() {
  const sourceLines = Math.max(1, cobolEditor.value.split("\n").length);
  const pythonLines = Math.max(1, pythonEditor.value.split("\n").length);
  sourceGutter.textContent = Array.from({ length: sourceLines }, (_, index) => index + 1).join("\n");
  pythonGutter.textContent = Array.from({ length: pythonLines }, (_, index) => index + 1).join("\n");
  sourceCount.textContent = `${sourceLines} lines`;
}

function setBusy(button, busy, label) {
  button.disabled = busy;
  if (busy) {
    button.dataset.label = button.innerHTML;
    button.textContent = label;
  } else if (button.dataset.label) {
    button.innerHTML = button.dataset.label;
    delete button.dataset.label;
  }
}

function showNotice(message, kind = "info", unsupported = []) {
  notice.replaceChildren();
  notice.classList.toggle("is-error", kind === "error");
  if (!message) return;
  notice.append(document.createTextNode(message));
  if (unsupported.length) {
    const list = document.createElement("ul");
    for (const item of unsupported) {
      const row = document.createElement("li");
      row.textContent = `Line ${item.line}: ${item.source}`;
      list.append(row);
    }
    notice.append(list);
  }
}

async function requestJson(url, payload) {
  const options = payload === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) {
    const error = new Error(result.error || `Request failed with status ${response.status}.`);
    error.payload = result;
    throw error;
  }
  return result;
}

async function translateSource() {
  showNotice("");
  setBusy(convertButton, true, "Converting...");
  runButton.disabled = true;
  copyButton.disabled = true;
  pythonEditor.value = "";
  pythonStatus.textContent = "Translating";
  runStatus.textContent = "Not run";
  runStatus.className = "run-status";
  programOutput.textContent = "Run the translated Python to see its output.";
  try {
    const result = await requestJson("/api/translate", { source: cobolEditor.value });
    pythonEditor.value = result.python;
    pythonStatus.textContent = "Translated";
    runButton.disabled = false;
    copyButton.disabled = false;
    showNotice("Translation completed. Review the generated code before running it.");
  } catch (error) {
    pythonStatus.textContent = "Translation stopped";
    showNotice(error.message, "error", error.payload?.unsupported || []);
  } finally {
    setBusy(convertButton, false);
    updateEditorMeta();
  }
}

async function runPython() {
  setBusy(runButton, true, "Running...");
  runStatus.textContent = "Running";
  runStatus.className = "run-status";
  programOutput.textContent = "";
  try {
    const result = await requestJson("/api/run", {
      python: pythonEditor.value,
      stdin: programInput.value,
    });
    const output = [result.stdout, result.stderr].filter(Boolean).join("\n");
    programOutput.textContent = output || "Program finished with no output.";
    if (result.exit_code === 0) {
      runStatus.textContent = "Finished · exit 0";
      runStatus.className = "run-status is-success";
    } else {
      runStatus.textContent = `Stopped · exit ${result.exit_code}`;
      runStatus.className = "run-status is-error";
    }
  } catch (error) {
    programOutput.textContent = error.message;
    runStatus.textContent = "Run failed";
    runStatus.className = "run-status is-error";
  } finally {
    setBusy(runButton, false);
  }
}

async function loadSample(name = "emi") {
  showNotice("");
  try {
    const sample = await requestJson(`/api/sample?name=${encodeURIComponent(name)}`);
    cobolEditor.value = sample.source;
    programInput.value = name === "emi" ? sampleInputs : "";
    updateEditorMeta();
    await translateSource();
  } catch (error) {
    showNotice(error.message, "error");
  }
}

document.querySelector("#load-sample").addEventListener("click", () => loadSample("emi"));
document.querySelector("#load-arith-sample").addEventListener("click", () => loadSample("arith-loop"));
document.querySelector("#load-counter-sample").addEventListener("click", () => loadSample("counter"));
convertButton.addEventListener("click", translateSource);
runButton.addEventListener("click", runPython);
cobolEditor.addEventListener("input", () => {
  updateEditorMeta();
  pythonEditor.value = "";
  pythonStatus.textContent = "Source changed";
  runButton.disabled = true;
  copyButton.disabled = true;
});
cobolEditor.addEventListener("scroll", () => { sourceGutter.scrollTop = cobolEditor.scrollTop; });
pythonEditor.addEventListener("scroll", () => { pythonGutter.scrollTop = pythonEditor.scrollTop; });
document.querySelector("#source-file").addEventListener("change", async (event) => {
  const [file] = event.target.files;
  if (!file) return;
  cobolEditor.value = await file.text();
  updateEditorMeta();
  showNotice(`Loaded ${file.name}.`);
  pythonEditor.value = "";
  pythonStatus.textContent = "Source changed";
  runButton.disabled = true;
  copyButton.disabled = true;
});
copyButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(pythonEditor.value);
    showNotice("Python copied to clipboard.");
  } catch {
    showNotice("Clipboard access is unavailable in this browser.", "error");
  }
});
document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    if (!convertButton.disabled) translateSource();
  }
});

programInput.value = sampleInputs;
updateEditorMeta();
loadSample();