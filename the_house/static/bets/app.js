function getMargin(form) {
  const input = form.querySelector(`[name=${window.MARGIN_INPUT_NAME}]`);
  const v = parseFloat(input?.value || '0');
  return isNaN(v) ? 0 : v;
}

function setupOutcomeBuilder(initialOutcomes) {
  const form = document.getElementById('market-form');
  const container = document.getElementById('outcomes');
  const preview = document.getElementById('odds-preview');
  const addBtn = document.getElementById('add-outcome');
  let rows = [];

  const clamp = (v, min, max) => Math.min(max, Math.max(min, v|0)); // int clamp

  function createRow(title = '', weight = 0) {
    const idx = rows.length;
    const row = document.createElement('div');
    row.className = 'outcome-row';
    row.innerHTML = `
      <input type="text" name="outcomes[${idx}][title]" placeholder="Outcome title" value="${title}" required />
      <input type="range" min="0" max="100" step="1" value="${clamp(weight,0,100)}" data-weight-slider />
      <input type="number" min="0" max="100" step="1" name="outcomes[${idx}][weight]" value="${clamp(weight,0,100)}" data-weight-number />
      <button type="button" data-remove>&times;</button>
    `;

    const slider = row.querySelector('[data-weight-slider]');
    const number = row.querySelector('[data-weight-number]');

    // keep in sync (slider → number)
    slider.addEventListener('input', () => {
      number.value = clamp(parseInt(slider.value || '0', 10), 0, 100);
      renderPreview();
    });

    // keep in sync (number → slider), clamp & coerce integer
    const syncFromNumber = () => {
      const v = clamp(parseInt(number.value || '0', 10), 0, 100);
      number.value = v;
      slider.value = v;
      renderPreview();
    };
    number.addEventListener('input', syncFromNumber);
    number.addEventListener('change', syncFromNumber);

    row.querySelector('[data-remove]').addEventListener('click', () => {
      rows = rows.filter(r => r !== row);
      row.remove();
      reindex();
      renderPreview();
    });

    rows.push(row);
    container.appendChild(row);
  }

  function reindex() {
    rows.forEach((row, i) => {
      row.querySelectorAll('[name]').forEach(el => {
        if (el.name.includes('title'))  el.name = `outcomes[${i}][title]`;
        if (el.name.includes('weight')) el.name = `outcomes[${i}][weight]`; // number input only
      });
    });
  }

  function adjustDisplayOdds(raw) {
    const r = Number(raw);
    if (r >= 1.01) return Number(r.toFixed(2));

    const rFloor = Math.max(r, 1.001);
    const x = Math.min(Math.max((rFloor - 1.0) / 0.01, 0), 0.999999);
    const alpha = 6.0;
    const y = Math.log1p(alpha * x) / Math.log1p(alpha);
    const val = 1.001 + 0.009 * y;
    return Number(val.toFixed(3));
  }

  function renderPreview() {
    const numbers = rows.map(row => row.querySelector('[data-weight-number]'));
    const weights = numbers.map(n => clamp(parseInt(n.value || '0', 10), 0, 100));
    const titles  = rows.map(row => row.querySelector('input[type="text"]').value || 'Outcome');
    const total   = weights.reduce((a,b)=>a+b,0);
    const mInput  = form.querySelector(`[name=${window.MARGIN_INPUT_NAME}]`);
    const m       = parseFloat(mInput?.value || '0');
    const over    = 1 + (isNaN(m) ? 0 : m);

    preview.innerHTML = '';
    rows.forEach((_, i) => {
      const fairP  = total === 0 ? (1/rows.length) : (weights[i]/total);
      const pPrime = fairP * over;
      const raw    = pPrime === 0 ? 999.99 : (1 / pPrime);
      const odds   = adjustDisplayOdds(raw);
      const card = document.createElement('div');
      card.className = 'preview-card';
      card.innerHTML = `
        <div><strong>${titles[i] || 'Outcome ' + (i+1)}</strong></div>
        <div>Implied %: ${(pPrime*100).toFixed(2)}%</div>
        <div>Odds: ${odds.toFixed(odds >= 1.01 ? 2 : 3)}</div>
      `;
      preview.appendChild(card);
    });
  }


  addBtn?.addEventListener('click', () => { createRow('', 0); renderPreview(); });
  (initialOutcomes || []).forEach(o => createRow(o.title, o.weight));
  form?.addEventListener('input', (e) => {
    if (e.target.name === window.MARGIN_INPUT_NAME) renderPreview();
  });
  renderPreview();
}

