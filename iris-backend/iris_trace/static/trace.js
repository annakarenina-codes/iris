'use strict';
const $ = id => document.getElementById(id);
const views = new Map();
let selected = null,
  offset = 0,
  total = 0,
  busy = false,
  failures = 0;
const text = v => typeof v === 'string' ? v : v?.preview ?? JSON.stringify(v ?? '');
const pretty = v => JSON.stringify(v ?? null, null, 2);

function el(tag, txt, cls) {
  const x = document.createElement(tag);
  if (txt !== undefined) x.textContent = txt;
  if (cls) x.className = cls;
  return x
}

function button(label, fn) {
  const x = el('button', label);
  x.type = 'button';
  x.addEventListener('click', fn);
  return x
}

function jsonDetails(label, value) {
  const d = el('details');
  d.append(el('summary', label), el('pre', pretty(value)));
  return d
}
async function api(path, options = {}) {
  const r = await fetch('/debug' + path, {
    cache: 'no-store',
    ...options
  });
  if (!r.ok) {
    let message = `Request failed (${r.status})`;
    try {
      message = (await r.json()).error || message
    } catch {}
    throw Error(message)
  }
  return r.json()
}

function remember() {
  try {
    sessionStorage.setItem('iris-trace-tabs', JSON.stringify({
      ids: [...views.keys()],
      selected
    }));
  } catch {}
}

function select(id) {
  selected = id;
  for (const [key, v] of views) {
    v.root.hidden = key !== id;
    v.tab.setAttribute('aria-selected', String(key === id));
    v.tab.tabIndex = key === id ? 0 : -1
  }
  $('empty').hidden = !!id;
  remember();
  if (id) history.replaceState(null, '', '/debug/trace/' + id)
}

function close(id) {
  const v = views.get(id);
  if (!v) return;
  v.root.remove();
  v.wrap.remove();
  views.delete(id);
  if (selected === id) select(views.keys().next().value || null);
  remember()
}

function open(id) {
  if (!/^[a-f0-9]{32}$/.test(id)) return;
  if (views.has(id)) {
    select(id);
    return
  }
  const v = {
    id,
    events: new Map(),
    spans: new Map(),
    claims: new Map(),
    revision: 0,
    claim: '',
    pane: 'Pipeline',
    terminal: false
  };
  views.set(id, v);
  v.wrap = el('div', undefined, 'tab');
  v.tab = button(id.slice(0, 8), () => select(id));
  v.tab.setAttribute('role', 'tab');
  v.tab.id = 'tab-' + id;
  v.tab.setAttribute('aria-controls', 'workspace-' + id);
  const closer = button('\xd7', () => close(id));
  closer.className = 'close';
  closer.setAttribute('aria-label', 'Close request ' + id.slice(0, 8));
  v.wrap.append(v.tab, closer);
  $('tabs').append(v.wrap);
  v.root = el('section', undefined, 'workspace');
  v.root.id = 'workspace-' + id;
  v.root.setAttribute('role', 'tabpanel');
  v.root.setAttribute('aria-labelledby', v.tab.id);
  v.heading = el('h2', 'Loading request\u2026');
  v.stats = el('div', undefined, 'stats');
  v.tools = el('div', undefined, 'tools');
  const exp = el('a', 'Export trace', 'action');
  exp.href = '/debug/traces/' + id + '/export';
  v.tools.append(exp, button('Refresh', () => update(v, true)), button('Delete saved trace', async () => {
    if (!confirm('Delete this saved trace and its artifacts?')) return;
    try {
      await api('/traces/' + id, {
        method: 'DELETE',
        headers: {
          'X-Trace-Action': '1'
        }
      });
      close(id);
      await refresh()
    } catch (e) {
      $('notice').textContent = e.message
    }
  }));
  const claimLabel = el('label', 'Claim scope');
  v.claimSelect = el('select');
  v.claimSelect.setAttribute('aria-label', 'Claim scope');
  v.claimSelect.append(new Option('Request overview', ''));
  claimLabel.append(v.claimSelect);
  v.claimSelect.onchange = () => {
    v.claim = v.claimSelect.value;
    filterStages(v);
    renderClaims(v)
  };
  v.nav = el('nav', undefined, 'subnav');
  v.nav.setAttribute('aria-label', 'Request views');
  v.panels = {};
  for (const name of ['Pipeline', 'Claims', 'Evidence', 'Decisions', 'Input and OCR', 'Diagnostics']) {
    const pane = el('section', undefined, 'panel');
    pane.hidden = name !== v.pane;
    v.panels[name] = pane;
    const b = button(name, () => {
      v.pane = name;
      for (const [n, p] of Object.entries(v.panels)) p.hidden = n !== name;
      for (const n of v.nav.children) n.setAttribute('aria-pressed', String(n === b))
    });
    b.setAttribute('aria-pressed', String(name === v.pane));
    v.nav.append(b)
  }
  v.root.append(v.heading, v.stats, v.tools, claimLabel, v.nav, ...Object.values(v.panels));
  $('workspaces').append(v.root);
  select(id);
  update(v);
}

function badge(label, kind) {
  return el('span', label, 'badge ' + (kind || label))
}

function domainKind(event) {
  if (event.status === 'error') return 'error';
  if (/error|missing|failed|unavailable/.test(event.domain_outcome || '')) return 'warning';
  return event.status || 'running'
}

function filterStages(v) {
  for (const row of v.spans.values()) row.node.hidden = !!v.claim && !!row.claim && row.claim !== v.claim
}

function addSpan(v, e) {
  let row = v.spans.get(e.span_id);
  if (!row) {
    const node = el('details', undefined, 'stage');
    const summary = el('summary');
    const pre = el('pre');
    const children = el('div', undefined, 'children');
    node.append(summary, pre, children);
    row = {
      node,
      summary,
      pre,
      children,
      start: null,
      end: null
    };
    v.spans.set(e.span_id, row);
    v.panels.Pipeline.append(node)
  }
  if (e.kind === 'span.start') row.start = e;
  else row.end = e;
  const s = row.start || e,
    done = row.end;
  row.claim = s.claim_id;
  const parent = v.spans.get(s.parent_span_id);
  if (parent && row.node.parentNode !== parent.children) parent.children.append(row.node);
  row.summary.replaceChildren(el('span', s.stage_id + ' '), badge(done ? domainKind(done) : 'running'), el('span', done ? ' \xb7 ' + Math.round(done.duration_ms || 0) + ' ms' : ''));
  if (done?.domain_outcome) row.summary.append(el('span', ' \xb7 ' + done.domain_outcome));
  if (row.claim) row.summary.append(el('span', ' \xb7 Claim ' + row.claim));
  row.pre.textContent = pretty({
    execution: done?.status || 'running',
    domain_outcome: done?.domain_outcome,
    calibration: 'not_evaluated',
    input: s.input,
    output: done?.output,
    error: done?.error
  });
}

function renderClaims(v) {
  const claimPane = v.panels.Claims,
    evidence = v.panels.Evidence;
  claimPane.replaceChildren();
  evidence.replaceChildren();
  for (const [id, c] of v.claims) {
    if (v.claim && v.claim !== id) continue;
    const card = el('article', undefined, 'card');
    card.append(el('h3', 'Claim ' + id), el('p', text(c.claim_text || c.normalized_claim), 'claimtext'), badge(c.verdict || 'awaiting result'), el('p', text(c.message || '')), jsonDetails('Claim transformations and metadata', c));
    claimPane.append(card);
    const sources = c.evidence_sources || c.sources || c.supporting_sources || [];
    for (const source of Array.isArray(sources) ? sources : []) {
      const box = el('article', undefined, 'card');
      box.append(el('h3', text(source.title || source.source || 'Evidence')), el('p', 'Claim ' + id));
      try {
        const url = new URL(source.url);
        if (['https:', 'http:'].includes(url.protocol)) {
          const a = el('a', 'Open source');
          a.href = url.href;
          a.target = '_blank';
          a.rel = 'noopener noreferrer';
          box.append(a)
        }
      } catch {}
      box.append(jsonDetails('Evidence details', source));
      evidence.append(box)
    }
  }
  if (!claimPane.children.length) claimPane.append(el('p', 'No extracted claims yet. Check the pipeline for routing, early exits or errors.', 'empty-state'));
  if (!evidence.children.length) evidence.append(el('p', 'No public evidence attached yet. Retrieval inputs and rejected candidates remain inspectable in the pipeline.', 'empty-state'));
  for (const id of v.claims.keys())
    if (![...v.claimSelect.options].some(o => o.value === id)) v.claimSelect.append(new Option('Claim ' + id, id));
}

function addDecision(v, e) {
  if (e.kind === 'span.start' || e.kind === 'span.end') return;
  const target = e.kind.startsWith('request.input') || e.kind === 'ocr.selection' ? v.panels['Input and OCR'] : e.kind.startsWith('verdict.') || e.kind === 'claim.final' || e.kind === 'text.route' || e.kind.startsWith('calibration.') ? v.panels.Decisions : v.panels.Diagnostics;
  const detail = jsonDetails(e.kind + ' \xb7 ' + Math.round(e.offset_ms) + ' ms', e.data ?? e);
  detail.dataset.event = String(e.seq);
  target.append(detail)
}

function renderOCR(v, e) {
  if (v.ocrRendered) return;
  const data = e.data,
    regions = data?.raw_regions;
  if (!Array.isArray(regions)) return;
  const image = v.data.artifacts.find(a => a.kind === 'image');
  if (!image) return;
  v.ocrRendered = true;
  const wrap = el('div', undefined, 'card');
  wrap.append(el('h3', 'OCR region overlay'));
  const ns = 'http://www.w3.org/2000/svg',
    svg = document.createElementNS(ns, 'svg');
  svg.classList.add('ocr-view');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', 'OCR regions on the input image. Green retained, red excluded.');
  const pre = data.image?.preprocessing || {},
    original = data.image?.original_size || [1000, 1000];
  const size = pre.normalized_size || pre.processed_size || pre.resized_size || original;
  const w = size[0],
    h = size[1];
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  svg.setAttribute('width', String(w));
  const img = document.createElementNS(ns, 'image');
  img.setAttribute('href', '/debug/artifacts/' + image.id);
  img.setAttribute('width', w);
  img.setAttribute('height', h);
  img.setAttribute('preserveAspectRatio', 'none');
  svg.append(img);
  const selected = new Set((data.retained || []).map(r => JSON.stringify(r.bbox)));
  regions.forEach((r, i) => {
    if (!Array.isArray(r.bbox)) return;
    const polygon = document.createElementNS(ns, 'polygon');
    polygon.setAttribute('points', r.bbox.map(p => p.join(',')).join(' '));
    polygon.classList.add(selected.has(JSON.stringify(r.bbox)) ? 'ocr-retained' : 'ocr-rejected');
    const title = document.createElementNS(ns, 'title');
    title.textContent = `Region ${i+1}: ${r.text} (${r.confidence??'unknown confidence'})`;
    polygon.append(title);
    svg.append(polygon)
  });
  wrap.append(el('p', 'Green: retained. Red: excluded. Inspect the selection event below for text, confidence and reasons.'), svg);
  v.panels['Input and OCR'].prepend(wrap)
}
async function update(v, force = false) {
  if (v.loading || v.terminal && !force) return;
  v.loading = true;
  try {
    const data = await api('/traces/' + v.id + '/events?after=' + v.revision);
    v.data = data;
    v.terminal = data.status !== 'running';
    v.heading.textContent = data.title || 'Request';
    v.tab.textContent = data.id.slice(0, 8) + ' \xb7 ' + data.status;
    v.tab.title = data.title;
    v.stats.replaceChildren(badge(data.status), badge(data.platform), badge(data.input_type), badge('Capture: ' + data.capture_status, data.capture_status === 'partial' ? 'warning' : ''), el('span', new Date(data.created * 1000).toLocaleString()), el('span', (data.summary.duration_ms !== undefined ? Math.round(data.summary.duration_ms) + ' ms' : 'Processing\u2026')));
    if (data.summary.calibration_result) v.stats.append(badge('Calibration: ' + data.summary.calibration_result, data.summary.calibration_result));
    for (const e of data.events) {
      if (v.events.has(e.seq)) continue;
      v.events.set(e.seq, e);
      if (e.kind.startsWith('span.')) addSpan(v, e);
      else addDecision(v, e);
      if (e.kind === 'claim.final' && e.data?.result) v.claims.set(String(e.data.result.claim_id), e.data.result);
      if (e.kind === 'request.result') {
        for (const c of e.data?.claims || [])
          if (c.claim_id !== undefined) v.claims.set(String(c.claim_id), c)
      }
      if (e.kind === 'span.end' && e.stage_id === 'claims.extract') {
        for (const c of e.output?.claims || [])
          if (c.claim_id !== undefined && !v.claims.has(String(c.claim_id))) v.claims.set(String(c.claim_id), c)
      }
    }
    v.revision = data.revision;
    filterStages(v);
    if (data.events.some(e => e.kind === 'claim.final' || e.kind === 'request.result' || e.stage_id === 'claims.extract')) renderClaims(v);
    for (const e of v.events.values())
      if (e.kind === 'ocr.selection') renderOCR(v, e);
  } catch (e) {
    v.stats.replaceChildren(badge(e.message, 'error'));
    if (/404/.test(e.message)) {
      v.missing = (v.missing || 0) + 1;
      v.terminal = v.missing >= 3;
      v.heading.textContent = v.terminal ? 'Trace expired or deleted' : 'Waiting for trace storage\u2026'
    }
  } finally {
    v.loading = false
  }
}
async function refresh() {
  if (busy) return;
  busy = true;
  try {
    const data = await api('/traces?offset=' + offset + '&q=' + encodeURIComponent($('search').value) + '&status=' + encodeURIComponent($('status').value));
    total = data.total;
    $('history-count').textContent = `${total} requests \xb7 showing ${offset+1}\u2013${Math.min(offset+data.items.length,total)}`;
    $('previous').disabled = offset === 0;
    $('next').disabled = offset + 40 >= total;
    const ids = new Set(data.items.map(r => r.id));
    for (const old of [...$('history').children])
      if (!ids.has(old.dataset.id)) old.remove();
    for (const r of data.items) {
      let b = [...$('history').children].find(x => x.dataset.id === r.id);
      if (!b) {
        b = button('', () => open(r.id));
        b.className = 'history-item';
        b.dataset.id = r.id;
        $('history').append(b)
      }
      b.replaceChildren(el('span', r.title), el('small', r.id.slice(0, 8) + ' \xb7 ' + r.platform + ' \xb7 ' + new Date(r.created * 1000).toLocaleTimeString()), badge(r.status));
    }
    data.items.forEach((r, i) => {
      const b = [...$('history').children].find(x => x.dataset.id === r.id);
      if ($('history').children[i] !== b) $('history').insertBefore(b, $('history').children[i] || null)
    });
    $('notice').textContent = data.health.error || '';
    failures = 0;
    if ($('follow').checked && data.items[0] && offset === 0) open(data.items[0].id);
    await Promise.all([...views.values()].map(v => update(v)));
  } catch (e) {
    failures++;
    $('notice').textContent = e.message + '; retrying with backoff.'
  } finally {
    busy = false
  }
}
$('refresh').onclick = () => {
  for (const v of views.values()) v.terminal = false;
  refresh()
};
let searchTimer;
$('search').oninput = () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    offset = 0;
    refresh()
  }, 250)
};
$('status').onchange = () => {
  offset = 0;
  refresh()
};
$('previous').onclick = () => {
  offset = Math.max(0, offset - 40);
  refresh()
};
$('next').onclick = () => {
  offset += 40;
  refresh()
};
$('close-others').onclick = () => {
  for (const id of [...views.keys()])
    if (id !== selected) close(id)
};
$('tabs').onkeydown = e => {
  if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(e.key)) return;
  const buttons = [...$('tabs').querySelectorAll('[role=tab]')];
  let i = buttons.indexOf(document.activeElement);
  if (i < 0) return;
  e.preventDefault();
  i = e.key === 'Home' ? 0 : e.key === 'End' ? buttons.length - 1 : (i + (e.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
  buttons[i].click();
  buttons[i].focus()
};
$('run-case').onclick = async () => {
  const b = $('run-case');
  b.disabled = true;
  try {
    const data = JSON.parse($('case').value);
    const result = await api('/calibration/runs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Trace-Action': '1'
      },
      body: JSON.stringify(data)
    });
    $('run-message').textContent = 'Run started.';
    open(result.trace_id);
    await refresh()
  } catch (e) {
    $('run-message').textContent = e.message
  } finally {
    b.disabled = false
  }
};
$('compare').onclick = async () => {
  const result = $('comparison');
  result.replaceChildren();
  try {
    const [a, b] = await Promise.all([api('/traces/' + $('baseline').value.trim()), api('/traces/' + $('candidate').value.trim())]);
    const records = t => {
        const map = new Map();
        for (const e of t.events)
          if (e.kind === 'span.end') {
            const key = (e.claim_id || 'request') + ' / ' + e.stage_id;
            const list = map.get(key) || [];
            list.push(e.output);
            map.set(key, list)
          } return map
      },
      left = records(a),
      right = records(b);
    let count = 0;
    for (const key of new Set([...left.keys(), ...right.keys()])) {
      if (pretty(left.get(key)) === pretty(right.get(key))) continue;
      count++;
      const card = el('details', undefined, 'card');
      card.append(el('summary', key + ' \xb7 output changed'));
      const grid = el('div', undefined, 'diff-grid');
      grid.append(el('pre', 'Baseline\n' + pretty(left.get(key))), el('pre', 'Candidate\n' + pretty(right.get(key))));
      card.append(grid);
      result.append(card)
    }
    result.prepend(el('p', count ? `${count} stage groups differ. Differences are observations, not automatic correctness failures.` : 'No captured stage-output differences. Check capture completeness and run configuration.'));
  } catch (e) {
    result.textContent = e.message
  }
};
try {
  const saved = JSON.parse(sessionStorage.getItem('iris-trace-tabs') || '{}');
  for (const id of (saved.ids || []).slice(0, 15)) open(id);
  if (views.has(saved.selected)) select(saved.selected)
} catch {}
const linked = location.pathname.split('/').pop();
if (/^[a-f0-9]{32}$/.test(linked)) open(linked);
refresh();
async function poll() {
  if (!document.hidden) await refresh();
  setTimeout(poll, Math.min(30000, 2000 * 2 ** failures))
}
setTimeout(poll, 2000);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) refresh()
});
