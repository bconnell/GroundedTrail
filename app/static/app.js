'use strict';

const $ = (id) => document.getElementById(id);
const state = { documents: [], ready: false };

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}

function toast(message) {
  const node = $('toast');
  node.textContent = message;
  node.classList.remove('hidden');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => node.classList.add('hidden'), 5000);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      if (typeof payload.detail === 'string') message = payload.detail;
    } catch (_) { /* The server did not return JSON. */ }
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

function activate(name) {
  document.querySelectorAll('[data-tab]').forEach(button => {
    button.classList.toggle('active', button.dataset.tab === name);
    button.setAttribute('aria-current', button.dataset.tab === name ? 'page' : 'false');
    const dot = button.querySelector('.nav-active-dot');
    if (dot) dot.remove();
    if (button.dataset.tab === name) button.append(element('span', 'nav-active-dot'));
  });
  document.querySelectorAll('.page').forEach(page => page.classList.add('hidden'));
  $(`page-${name}`).classList.remove('hidden');
  $('section-label').textContent = name[0].toUpperCase() + name.slice(1);
}

async function loadDocuments() {
  const result = await api('/api/documents');
  state.documents = result.documents;
  $('metric-docs').textContent = String(result.documents.length);
  $('side-doc-count').textContent = String(result.documents.length);
  $('library-count').textContent = `${result.documents.length} sources`;
  const list = $('doc-list');
  list.replaceChildren();
  if (!result.documents.length) {
    list.append(element('p', '', 'No documents indexed. Add a source above to begin.'));
  }
  for (const document of result.documents) {
    const card = element('article', 'document-card');
    const details = element('div');
    details.append(element('h3', '', document.name));
    details.append(element('p', '', `${document.chunk_count} passages · SHA-256 ${document.sha256.slice(0, 10)}…`));
    const actions = element('div');
    const remove = element('button', 'danger', 'Delete');
    remove.type = 'button';
    remove.setAttribute('aria-label', `Delete ${document.name}`);
    remove.addEventListener('click', async () => {
      if (!window.confirm(`Delete ${document.name} and all indexed passages?`)) return;
      remove.disabled = true;
      try {
        await api(`/api/documents/${encodeURIComponent(document.id)}`, { method: 'DELETE' });
        await loadDocuments();
        toast('Document removed.');
      } catch (error) {
        remove.disabled = false;
        toast(error.message);
      }
    });
    actions.append(remove);
    card.append(details, actions);
    list.append(card);
  }
}

function renderResults(result) {
  $('metric-results').textContent = String(result.source_count);
  const area = $('query-results');
  area.replaceChildren();
  const titleRow = element('div', 'result-head');
  titleRow.append(element('h2', '', 'Evidence review'));
  titleRow.append(element('span', '', `${result.source_count} source passages`));
  area.append(titleRow);
  const answer = element('section', 'answer-card');
  const label = result.mode === 'generated_unverified' ? 'MODEL ANSWER · UNVERIFIED' :
    result.mode === 'retrieval' ? 'RETRIEVAL ONLY' : 'NO EVIDENCE';
  answer.append(element('span', 'badge', label));
  answer.append(element('p', '', result.answer));
  area.append(answer);
  for (const source of result.sources) {
    const card = element('article', 'source-card');
    const top = element('div', 'source-top');
    const left = element('div');
    left.append(element('span', 'source-number', `[${source.citation}]`));
    left.append(element('span', 'source-name', source.name));
    top.append(left);
    top.append(element('span', 'source-meta', `PASSAGE ${source.chunk_index}`));
    card.append(top);
    card.append(element('p', '', source.excerpt));
    area.append(card);
  }
}

async function search(event) {
  event.preventDefault();
  const button = $('search-button');
  button.disabled = true;
  try {
    const result = await api('/api/ask', {
      method: 'POST',
      body: JSON.stringify({ question: $('question').value, top_k: Number($('top-k').value) })
    });
    renderResults(result);
  } catch (error) {
    toast(error.message);
  } finally { button.disabled = false; }
}

async function upload(event) {
  event.preventDefault();
  const button = $('upload-button');
  button.disabled = true;
  try {
    await api('/api/documents', {
      method: 'POST',
      body: JSON.stringify({ name: $('doc-name').value.trim(), content: $('doc-content').value })
    });
    $('upload-form').reset();
    toast('Document indexed and ready for retrieval.');
    await loadDocuments();
  } catch (error) {
    toast(error.message);
  } finally { button.disabled = false; }
}

async function evaluate() {
  const button = $('evaluate-button');
  button.disabled = true;
  try {
    const result = await api('/api/evaluation');
    const area = $('eval-results');
    area.replaceChildren();
    const metrics = element('div', 'eval-scores');
    for (const [name, value] of [
      ['REFERENCE CASES', String(result.case_count)],
      [`HIT RATE @ ${result.k}`, `${(result.hit_rate * 100).toFixed(1)}%`],
      ['MEAN RECIPROCAL RANK', result.mrr.toFixed(3)]
    ]) {
      const card = element('div', 'eval-score');
      card.append(element('small', '', name), element('strong', '', value));
      metrics.append(card);
    }
    area.append(metrics);
    for (const resultCase of result.cases) {
      const card = element('article', 'eval-case');
      card.append(element('strong', '', `${resultCase.hit ? '✓' : '○'} ${resultCase.question}`));
      card.append(element('p', '', `Expected ${resultCase.expected_source} · Returned ${resultCase.retrieved_sources.join(', ') || 'none'}`));
      area.append(card);
    }
  } catch (error) { toast(error.message); }
  finally { button.disabled = false; }
}

async function initialize() {
  document.querySelectorAll('[data-tab]').forEach(button =>
    button.addEventListener('click', () => activate(button.dataset.tab)));
  $('search-form').addEventListener('submit', search);
  $('upload-form').addEventListener('submit', upload);
  $('evaluate-button').addEventListener('click', evaluate);
  $('source-file').addEventListener('change', async event => {
    const file = event.target.files[0];
    if (!file) return;
    if (!/\.(md|txt)$/i.test(file.name) || file.size > 120000) {
      toast('Select a .md or .txt file up to 120 KB.');
      return;
    }
    $('doc-name').value = file.name;
    $('doc-content').value = await file.text();
  });
  try {
    const health = await api('/api/health');
    $('status-dot').classList.add('ready');
    $('backend-label').textContent = health.backend === 'postgres' ? 'PostgreSQL connected' : 'Temporary demo storage';
    $('metric-mode').textContent = health.generation_enabled ? 'LLM + RAG' : 'Retrieval';
    $('mode-hint').textContent = health.generation_enabled ? 'Generated answers, inspect citations' : 'Source first, citation ready';
    await loadDocuments();
  } catch (error) {
    $('backend-label').textContent = 'Service unavailable';
    toast(error.message);
  }
}

document.addEventListener('DOMContentLoaded', initialize);
