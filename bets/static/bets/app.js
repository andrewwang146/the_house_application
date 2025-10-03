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


    function createRow(title = '', weight = 0) {
        const idx = rows.length;
        const row = document.createElement('div');
        row.className = 'outcome-row';
        row.innerHTML = `
            <input type="text" name="outcomes[${idx}][title]" placeholder="Outcome title" value="${title}" required />
            <span class="badge">Weight: <span data-weight>${weight}</span></span>
            <input type="range" min="0" max="100" step="1" name="outcomes[${idx}][weight]" value="${weight}" />
            <button type="button" data-remove>&times;</button>
        `;
        const slider = row.querySelector('input[type="range"]');
        const weightLabel = row.querySelector('[data-weight]');
        slider.addEventListener('input', () => { weightLabel.textContent = slider.value; renderPreview(); });
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
                if (el.name.includes('title')) el.name = `outcomes[${i}][title]`;
                if (el.name.includes('weight')) el.name = `outcomes[${i}][weight]`;
            });
        });
    }


    function renderPreview() {
        const weights = rows.map(row => parseInt(row.querySelector('input[type="range"]').value || '0', 10));
        const titles = rows.map(row => row.querySelector('input[type="text"]').value || 'Outcome');
        const total = weights.reduce((a,b)=>a+b,0);
        const m = parseFloat(getMargin(form));
        const overround = 1 + (isNaN(m) ? 0 : m);


        preview.innerHTML = '';
        rows.forEach((row, i) => {
            const fairP = total === 0 ? (1/rows.length) : (weights[i]/total);
            const pPrime = fairP * overround;
            const odds = pPrime === 0 ? 999.99 : (1 / pPrime);
            const card = document.createElement('div');
            card.className = 'preview-card';
            card.innerHTML = `
                <div><strong>${titles[i] || 'Outcome ' + (i+1)}</strong></div>
                <div>Implied %: ${(pPrime*100).toFixed(2)}%</div>
                <div>Odds: ${odds.toFixed(2)}</div>
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