const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const state = {
  source: "url",
  llmReady: false,
  busy: false,
  reportMarkdown: "",
  loadingTimer: null,
};

const elements = {};

document.addEventListener("DOMContentLoaded", () => {
  Object.assign(elements, {
    form: $("#matchForm"),
    resumeInput: $("#resumeInput"),
    resumeDrop: $("#resumeDrop"),
    resumeFileName: $("#resumeFileName"),
    resumeFileMeta: $("#resumeFileMeta"),
    jobUrl: $("#jobUrl"),
    jobText: $("#jobText"),
    jobFile: $("#jobFile"),
    jobFileName: $("#jobFileName"),
    redactToggle: $("#redactToggle"),
    submitButton: $("#submitButton"),
    demoButton: $("#demoButton"),
    formError: $("#formError"),
    stateDot: $("#stateDot"),
    stateText: $("#stateText"),
    emptyState: $("#emptyState"),
    loadingState: $("#loadingState"),
    loadingTitle: $("#loadingTitle"),
    loadingCopy: $("#loadingCopy"),
    loadingSteps: $("#loadingSteps"),
    resultContent: $("#resultContent"),
    modeBadge: $("#modeBadge"),
    scoreStamp: $("#scoreStamp"),
    scoreValue: $("#scoreValue"),
    jobTitle: $("#jobTitle"),
    levelText: $("#levelText"),
    scoreNarrative: $("#scoreNarrative"),
    requirementCount: $("#requirementCount"),
    matchedCount: $("#matchedCount"),
    missingCount: $("#missingCount"),
    resumeSummary: $("#resumeSummary"),
    strengthList: $("#strengthList"),
    missingSkills: $("#missingSkills"),
    evidenceLedger: $("#evidenceLedger"),
    evidenceCount: $("#evidenceCount"),
    adviceList: $("#adviceList"),
    downloadReport: $("#downloadReport"),
    copyReport: $("#copyReport"),
    toggleRaw: $("#toggleRaw"),
    rawReport: $("#rawReport"),
    traceList: $("#traceList"),
    resultsTitle: $("#resultsTitle"),
    workspace: $(".workspace"),
    resultsPanel: $(".results"),
  });

  bindFileInput(elements.resumeInput, handleResumeSelection);
  bindFileInput(elements.jobFile, handleJobFileSelection);
  bindDropZone();
  bindTabs();
  bindActions();
  loadStatus();
});

function bindActions() {
  elements.form.addEventListener("submit", submitMatch);
  elements.demoButton.addEventListener("click", runDemo);
  elements.copyReport.addEventListener("click", copyReport);
  elements.toggleRaw.addEventListener("click", toggleRawReport);
}

function bindFileInput(input, handler) {
  input.addEventListener("change", () => handler(input.files[0] || null));
}

function handleResumeSelection(file) {
  const hasFile = Boolean(file);
  elements.resumeDrop.classList.toggle("has-file", hasFile);
  elements.resumeFileName.textContent = hasFile ? file.name : "拖入简历，或点击选择";
  elements.resumeFileMeta.textContent = hasFile
    ? `${formatBytes(file.size)} · ${file.type || "本地文件"}`
    : "文件只在本次分析中临时使用";
}

function handleJobFileSelection(file) {
  const label = elements.jobFile.closest(".file-compact");
  label.classList.toggle("has-file", Boolean(file));
  elements.jobFileName.textContent = file ? file.name : "选择岗位文件";
}

function bindDropZone() {
  ["dragenter", "dragover"].forEach((eventName) => {
    elements.resumeDrop.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.resumeDrop.classList.add("is-dragging");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    elements.resumeDrop.addEventListener(eventName, (event) => {
      event.preventDefault();
      elements.resumeDrop.classList.remove("is-dragging");
    });
  });
  elements.resumeDrop.addEventListener("drop", (event) => {
    const [file] = event.dataTransfer.files;
    if (!file) return;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    elements.resumeInput.files = transfer.files;
    handleResumeSelection(file);
  });
}

function bindTabs() {
  const tabs = $$(".source-tab");
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activateTab(tab));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      let nextIndex = index;
      if (event.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
      if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
      if (event.key === "Home") nextIndex = 0;
      if (event.key === "End") nextIndex = tabs.length - 1;
      activateTab(tabs[nextIndex]);
      tabs[nextIndex].focus();
    });
  });
}

function activateTab(tab) {
  state.source = tab.dataset.source;
  $$(".source-tab").forEach((item) => {
    const active = item === tab;
    item.classList.toggle("is-active", active);
    item.setAttribute("aria-selected", String(active));
    item.tabIndex = active ? 0 : -1;
  });
  const paneMap = {
    url: $("#urlPane"),
    text: $("#textPane"),
    file: $("#filePane"),
  };
  Object.entries(paneMap).forEach(([source, pane]) => {
    pane.hidden = source !== state.source;
  });
  clearError();
}

async function loadStatus() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    if (!response.ok) throw new Error("状态接口不可用");
    const status = await response.json();
    state.llmReady = Boolean(status.llm_ready);
    elements.stateDot.classList.toggle("is-ready", state.llmReady);
    elements.stateDot.classList.toggle("is-missing", !state.llmReady);
    elements.stateText.textContent = state.llmReady
      ? `LLM 已配置 · ${status.provider || "OpenAI-compatible"}`
      : "LLM 未配置 · 请设置 .env";
  } catch {
    elements.stateText.textContent = "服务状态未知";
  }
}

async function submitMatch(event) {
  event.preventDefault();
  if (state.busy) return;
  clearError();

  const resume = elements.resumeInput.files[0];
  if (!resume) {
    setError("请先选择一份简历。");
    elements.resumeInput.focus();
    return;
  }
  if (!state.llmReady) {
    setError("LLM 未配置。请先在 .env 中填写 OPENAI_API_KEY，然后重启 Web 服务。");
    return;
  }

  const formData = new FormData();
  formData.append("resume", resume);
  formData.append("redact_pii", String(elements.redactToggle.checked));

  if (state.source === "url") {
    const value = elements.jobUrl.value.trim();
    if (!value) {
      setError("请填写招聘页面链接。");
      elements.jobUrl.focus();
      return;
    }
    formData.append("job_url", value);
  } else if (state.source === "text") {
    const value = elements.jobText.value.trim();
    if (!value) {
      setError("请粘贴岗位职责或任职要求。");
      elements.jobText.focus();
      return;
    }
    formData.append("job_text", value);
  } else {
    const file = elements.jobFile.files[0];
    if (!file) {
      setError("请选择岗位文件。");
      elements.jobFile.focus();
      return;
    }
    formData.append("job_file", file);
  }

  await runAnalysis(() =>
    fetch("/api/match", {
      method: "POST",
      body: formData,
    }),
  );
}

async function runDemo() {
  if (state.busy) return;
  clearError();
  if (!state.llmReady) {
    setError("示例同样需要 LLM。请先在 .env 中配置 OPENAI_API_KEY。");
    return;
  }
  await runAnalysis(() =>
    fetch("/api/demo", {
      method: "POST",
    }),
  );
}

async function runAnalysis(requestFactory) {
  setBusy(true);
  showLoading();
  try {
    const [response] = await Promise.all([
      requestFactory(),
      wait(650),
    ]);
    const payload = await parseResponse(response);
    renderResult(payload);
    elements.loadingState.hidden = true;
    elements.emptyState.hidden = true;
    elements.resultContent.hidden = false;
    elements.resultsTitle.tabIndex = -1;
    elements.resultsTitle.focus({ preventScroll: true });
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const scrollTarget = window.matchMedia("(max-width: 1050px)").matches
      ? elements.resultsPanel
      : elements.workspace;
    scrollTarget.scrollIntoView({
      behavior: reduceMotion ? "auto" : "smooth",
      block: "start",
    });
  } catch (error) {
    hideLoading();
    elements.resultContent.hidden = true;
    elements.emptyState.hidden = false;
    setError(error.message || "分析失败，请检查输入后重试。");
  } finally {
    setBusy(false);
  }
}

async function parseResponse(response) {
  let payload = {};
  try {
    payload = await response.json();
  } catch {
    throw new Error("服务返回了无法解析的响应。");
  }
  if (!response.ok) {
    throw new Error(payload.detail || `请求失败（${response.status}）`);
  }
  return payload;
}

function showLoading() {
  elements.emptyState.hidden = true;
  elements.resultContent.hidden = true;
  elements.loadingState.hidden = false;
  const messages = [
    ["正在读取简历", "工具会提取文本，并按设置隐藏邮箱和电话号码。"],
    ["正在读取岗位", "支持招聘页面、粘贴正文或本地岗位文件。"],
    ["LLM 正在分析", "拆解全部岗位要求，逐项匹配简历证据并形成简历速览。"],
    ["正在保存报告", "匹配结果和修改建议会整理成可下载的 Markdown 文件。"],
  ];
  let index = 0;
  updateLoading(messages[index], index);
  clearInterval(state.loadingTimer);
  state.loadingTimer = setInterval(() => {
    index = Math.min(index + 1, messages.length - 1);
    updateLoading(messages[index], index);
  }, 900);
}

function updateLoading([title, copy], index) {
  elements.loadingTitle.textContent = title;
  elements.loadingCopy.textContent = copy;
  $$("li", elements.loadingSteps).forEach((item, itemIndex) => {
    item.classList.toggle("is-active", itemIndex === index);
  });
}

function hideLoading() {
  clearInterval(state.loadingTimer);
  state.loadingTimer = null;
  elements.loadingState.hidden = true;
}

function renderResult(payload) {
  const analysis = payload.analysis;
  if (!analysis) throw new Error("结果缺少匹配分析数据。");
  clearInterval(state.loadingTimer);
  state.loadingTimer = null;

  elements.modeBadge.hidden = false;
  elements.modeBadge.textContent = "LLM 结构化分析";
  elements.jobTitle.textContent = payload.job_title || "目标岗位";
  elements.levelText.textContent = analysis.level || "匹配分析";
  elements.scoreValue.textContent = String(analysis.score ?? 0);
  elements.scoreStamp.style.setProperty("--score", String(analysis.score ?? 0));
  elements.requirementCount.textContent = String(analysis.total_requirements ?? 0);
  elements.matchedCount.textContent = String(analysis.matched_count ?? 0);
  elements.missingCount.textContent = String(analysis.missing_requirements?.length ?? 0);
  elements.scoreNarrative.textContent =
    `LLM 从岗位中拆解出 ${analysis.total_requirements} 项要求，` +
    `其中 ${analysis.matched_count} 项在简历中找到了原文证据。`;

  elements.resumeSummary.textContent = analysis.resume_summary || "暂无简历速览。";
  renderStrengths(analysis.strengths || []);
  renderMissingRequirements(analysis.missing_requirements || []);
  renderEvidence(analysis.evidence || []);
  renderAdvice(analysis.recommendations || [], analysis.missing_requirements || []);

  state.reportMarkdown = payload.report?.markdown || "";
  elements.downloadReport.href = payload.report?.download_url || "#";
  elements.rawReport.textContent = state.reportMarkdown;
  elements.rawReport.hidden = true;
  elements.toggleRaw.setAttribute("aria-expanded", "false");
  elements.toggleRaw.textContent = "查看原文";
  elements.copyReport.textContent = "复制报告";
  renderTrace(payload.trace || []);
}

function renderStrengths(strengths) {
  elements.strengthList.replaceChildren();
  strengths.forEach((strength) => {
    const tag = document.createElement("span");
    tag.className = "strength-tag";
    tag.textContent = strength;
    elements.strengthList.append(tag);
  });
}

function renderMissingRequirements(requirements) {
  elements.missingSkills.replaceChildren();
  if (!requirements.length) {
    const tag = document.createElement("span");
    tag.className = "skill-tag is-empty";
    tag.textContent = "所有已拆解岗位要求均已找到简历证据";
    elements.missingSkills.append(tag);
    return;
  }
  requirements.forEach((requirement) => {
    const tag = document.createElement("span");
    tag.className = "skill-tag";
    tag.textContent = requirement;
    elements.missingSkills.append(tag);
  });
}

function renderEvidence(evidence) {
  const template = $("#evidenceRowTemplate");
  elements.evidenceLedger.replaceChildren();
  elements.evidenceCount.textContent = `共 ${evidence.length} 项`;
  evidence.forEach((item, index) => {
    const row = template.content.firstElementChild.cloneNode(true);
    row.classList.toggle("is-missing", !item.matched);
    const category = {
      technical: "技术",
      experience: "经验",
      education: "教育",
      soft: "软性",
    }[item.category] || item.category;
    const priority = item.priority === "preferred" ? "加分" : "核心";
    $("small", row).textContent =
      `${String(index + 1).padStart(2, "0")} · ${priority} · ${category}`;
    $("strong", row).textContent = item.requirement;
    $("blockquote", row).textContent = item.matched
      ? item.evidence || "已匹配，但未提取到单句证据"
      : "简历中未找到对应证据";
    elements.evidenceLedger.append(row);
  });
}

function renderAdvice(recommendations, missingRequirements) {
  const advice = [...recommendations];
  if (!advice.length && missingRequirements.length) {
    advice.push(`优先补齐或补充证据：${missingRequirements.slice(0, 3).join("、")}。`);
  }
  if (!advice.length) {
    advice.push("把与岗位最相关的项目移到简历前部，并用数字说明结果。");
  }
  elements.adviceList.replaceChildren();
  advice.slice(0, 5).forEach((text) => {
    const item = document.createElement("li");
    item.textContent = text;
    elements.adviceList.append(item);
  });
}

function renderTrace(trace) {
  elements.traceList.replaceChildren();
  if (!trace.length) {
    const item = document.createElement("li");
    item.textContent = "本次运行没有可显示的工具轨迹。";
    elements.traceList.append(item);
    return;
  }
  trace.forEach((event) => {
    const item = document.createElement("li");
    const name = document.createElement("code");
    name.textContent = event.tool;
    const status = document.createElement("span");
    status.textContent = event.ok ? "完成" : `失败：${event.error || "未知错误"}`;
    item.append(name, status);
    elements.traceList.append(item);
  });
}

async function copyReport() {
  if (!state.reportMarkdown) return;
  try {
    await navigator.clipboard.writeText(state.reportMarkdown);
  } catch {
    const textArea = document.createElement("textarea");
    textArea.value = state.reportMarkdown;
    textArea.style.position = "fixed";
    textArea.style.opacity = "0";
    document.body.append(textArea);
    textArea.select();
    document.execCommand("copy");
    textArea.remove();
  }
  elements.copyReport.textContent = "已复制";
  window.setTimeout(() => {
    elements.copyReport.textContent = "复制报告";
  }, 1600);
}

function toggleRawReport() {
  const opening = elements.rawReport.hidden;
  elements.rawReport.hidden = !opening;
  elements.toggleRaw.setAttribute("aria-expanded", String(opening));
  elements.toggleRaw.textContent = opening ? "收起原文" : "查看原文";
}

function setBusy(value) {
  state.busy = value;
  elements.submitButton.disabled = value;
  elements.demoButton.disabled = value;
  $("span", elements.submitButton).textContent = value ? "正在分析" : "开始证据匹配";
}

function setError(message) {
  elements.formError.textContent = message;
}

function clearError() {
  elements.formError.textContent = "";
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function wait(milliseconds) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}
