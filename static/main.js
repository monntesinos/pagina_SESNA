console.log('Gestor de Variables iniciado.');
let originalData = [], filteredData = [];
let currentSort = [];
let currentFileToUpload = null;
let allPreviewData = [];
let previewCurrentPage = 0;
const previewItemsPerPage = 10;
let currentPage = 1;
let itemsPerPage = 10;
let _currentOtraOpcionCancelCallback = null;

let folderPreviewData = [];
let folderGlobalMetadata = null;
let currentZipFilename = null;

function formatNumero(val, columna) {
    if (val === null || val === undefined || val === '') return '';
    const num = Number(val);
    if (!isNaN(num) && Number.isFinite(num)) {
        if (columna === 'año') {
            return String(Math.round(num));
        } else {
            return num.toFixed(1);
        }
    }
    return val;
}

function escapeHtml(unsafe) {
    if (unsafe == null) return '';
    return String(unsafe)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;')
        .replace(/`/g, '&#96;');
}

function openModal(id) { document.getElementById(id).style.display = 'flex'; }

function closeModal(id) {
    document.getElementById(id).style.display = 'none';
    if (id === 'modalFolderUpload') {
        resetFolderModal();
    }
}

function showToast(msg) {
    const c = document.getElementById('toast-container');
    const t = document.createElement('div');
    t.className = 'toast';
    t.textContent = msg;
    c.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 500); }, 3000);
}

function handleCloseOtraOpcionModal(callback = null) {
    closeModal('modalOtraOpcion');
    if (typeof callback === 'function') callback();
    else if (typeof _currentOtraOpcionCancelCallback === 'function') _currentOtraOpcionCancelCallback();
    _currentOtraOpcionCancelCallback = null;
}

function resetFolderModal() {
    folderPreviewData = [];
    folderGlobalMetadata = null;
    currentZipFilename = null;
    const previewContainer = document.getElementById('zipPreviewContainer');
    if (previewContainer) previewContainer.style.display = 'none';
    const logContainer = document.getElementById('folderLogMessages');
    if (logContainer) logContainer.style.display = 'none';
    const progressDiv = document.getElementById('zipProgress');
    if (progressDiv) progressDiv.style.display = 'none';
    const fileInput = document.getElementById('zipFileInput');
    if (fileInput) fileInput.value = '';
    document.getElementById('rowCount').textContent = '0';
    document.getElementById('zipPreviewTable').innerHTML = '';
    document.getElementById('folderLogContent').textContent = '';
}

function autoResize(el) {
    if (!el || el.tagName !== 'TEXTAREA') return;
    const minH = parseFloat(getComputedStyle(el).minHeight) || 24;
    el.style.height = 'auto';
    const h = Math.max(el.scrollHeight, minH);
    el.style.height = h + 'px';
}

function syncRowHeights(tr) {
    const controls = tr.querySelectorAll('.edit-control');
    if (!controls.length) return;
    controls.forEach(c => c.style.height = 'auto');
    let maxH = 0;
    controls.forEach(c => { if (c.scrollHeight > maxH) maxH = c.scrollHeight; });
    controls.forEach(c => c.style.height = maxH + 'px');
}

function autoResizeModal(el) {
    if (!el || el.tagName !== 'TEXTAREA') return;
    const minH = parseFloat(getComputedStyle(el).minHeight) || 32;
    const curH = el.offsetHeight;
    el.style.height = 'auto';
    const newH = Math.max(el.scrollHeight, minH);
    const lineH = parseFloat(getComputedStyle(el).lineHeight) || 20;
    const linesCur = Math.round(curH / lineH);
    const linesNew = Math.round(newH / lineH);
    if (Math.abs(newH - curH) > 5 || linesNew !== linesCur) {
        el.style.height = newH + 'px';
    } else {
        el.style.height = curH + 'px';
    }
}

function updateTemaOptions(tr, ejeValue, currentTema) {
    const idx = window.COLUMN_DEFINITIONS.findIndex(c => c.keyName === 'tema');
    if (idx === -1) return;
    const sel = tr.cells[idx + 1]?.querySelector('select');
    if (!sel) return;
    if (!ejeValue) { sel.innerHTML = '<option value="">-seleccionar-</option>'; return; }
    const ejeNum = ejeValue.charAt(0);
    const temaDef = window.COLUMN_DEFINITIONS.find(c => c.keyName === 'tema');
    let html = '<option value="">-seleccionar-</option>';
    (temaDef ? temaDef.options : []).forEach(opt => {
        if (opt.startsWith(ejeNum)) html += `<option value="${opt}" ${opt===currentTema?'selected':''}>${opt}</option>`;
    });
    html += '<option value="_OTRA_">Otra...</option>';
    sel.innerHTML = html;
}

async function openOpcionesModal(col, rowId, onDone, onCancel) {
    _currentOtraOpcionCancelCallback = onCancel;
    const modal = document.getElementById('modalOtraOpcion');
    const input = document.getElementById('otraOpcionInput');
    const btn = document.getElementById('btnConfirmOtra');
    document.getElementById('modalOtraTitle').textContent = 'Agregar ' + col.displayName;
    input.value = '';
    modal.style.display = 'flex';
    input.focus();
    requestAnimationFrame(() => setTimeout(() => autoResizeModal(input), 50));

    btn.onclick = async () => {
        const newVal = input.value.trim();
        if (!newVal) { handleCloseOtraOpcionModal(onCancel); return; }
        const resp = await fetch(`/api/catalog/${col.keyName}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: newVal })
        });
        if (!resp.ok) {
            handleCloseOtraOpcionModal(onCancel);
            showToast('Error al guardar nuevo valor.');
            return;
        }
        const data = await resp.json();
        if (data.status === 'already_exists') {
            showToast(`'${data.value}' ya existe.`);
            onDone(data.value);
            handleCloseOtraOpcionModal();
        } else if (data.status === 'suggestion') {
            openSuggestionModal(data.original_input, data.suggested_value,
                async (finalVal) => {
                    await addAndSaveOption(col, rowId, finalVal, onDone);
                    closeModal('modalSuggestion');
                },
                () => handleCloseOtraOpcionModal(onCancel)
            );
            closeModal('modalOtraOpcion');
        } else {
            await addAndSaveOption(col, rowId, newVal, onDone);
            handleCloseOtraOpcionModal();
        }
    };
}

async function addAndSaveOption(col, rowId, valueToAdd, onDone) {
    if (!col.options.includes(valueToAdd)) { col.options.push(valueToAdd); col.options.sort(); }
    const updateData = {};
    updateData[col.keyName] = valueToAdd;
    await fetch(`/api/variables/${rowId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updateData)
    });
    showToast('✓ Guardado');
    onDone(valueToAdd);
}

function openSuggestionModal(originalInput, suggestedValue, onAccept, onDecline) {
    document.getElementById('suggestionMessage').innerHTML =
        `Tu valor '<strong>${escapeHtml(originalInput)}</strong>' es similar a '<strong>${escapeHtml(suggestedValue)}</strong>'. ¿Deseas usar la sugerencia?`;
    openModal('modalSuggestion');
    document.getElementById('btnAcceptSuggestion').onclick = () => onAccept(suggestedValue);
    document.getElementById('btnDeclineSuggestion').onclick = () => onDecline(originalInput);
}

async function loadData() {
    const r = await fetch('/api/variables');
    originalData = await r.json();
    console.log(`✅ Datos cargados: ${originalData.length} registros.`);
    handleSearch();
}

function updateSortIndicators() {
    document.querySelectorAll('#headerRow th').forEach(th => {
        th.classList.remove('sorted-asc', 'sorted-desc');
        const key = th.dataset.key;
        if (key) {
            const sort = currentSort.find(s => s.key === key);
            if (sort) {
                th.classList.add(sort.dir === 'asc' ? 'sorted-asc' : 'sorted-desc');
            }
        }
        const orderSpan = th.querySelector('.sort-order');
        if (orderSpan) orderSpan.textContent = '';
    });
    currentSort.forEach((s, idx) => {
        const th = document.querySelector(`#headerRow th[data-key="${s.key}"]`);
        if (th) {
            let orderSpan = th.querySelector('.sort-order');
            if (!orderSpan) {
                orderSpan = document.createElement('span');
                orderSpan.className = 'sort-order';
                const div = th.querySelector('.th-content');
                if (div) div.appendChild(orderSpan);
            }
            orderSpan.textContent = ` ${idx + 1}`;
        }
    });
}

function handleSearch() {
    const q = (document.getElementById('searchInput')?.value || '').toLowerCase();
    let data = (originalData || []).filter(r =>
        Object.values(r).some(v => String(v).toLowerCase().includes(q))
    );
    if (currentSort.length > 0) {
        data.sort((a, b) => {
            for (const s of currentSort) {
                let va = String(a[s.key] || '');
                let vb = String(b[s.key] || '');
                const cmp = va.localeCompare(vb, undefined, { numeric: true });
                if (cmp !== 0) {
                    return s.dir === 'asc' ? cmp : -cmp;
                }
            }
            return 0;
        });
    }
    filteredData = data;
    currentPage = 1;
    document.querySelectorAll('.row-selector').forEach(cb => cb.checked = false);
    renderHeaders();
    renderTable();
    updateSortIndicators();
}

function setSort(key, dir, event) {
    const shift = event && event.shiftKey;
    if (!shift) {
        if (currentSort.length === 1 && currentSort[0].key === key && currentSort[0].dir === dir) {
            currentSort = [];
        } else {
            currentSort = [{ key, dir }];
        }
    } else {
        const existingIdx = currentSort.findIndex(s => s.key === key);
        if (existingIdx !== -1) {
            if (currentSort[existingIdx].dir === dir) {
                currentSort.splice(existingIdx, 1);
            } else {
                currentSort[existingIdx].dir = dir;
            }
        } else {
            currentSort.push({ key, dir });
        }
    }
    updateSortIndicators();
    handleSearch();
}

function renderHeaders() {
    const hr = document.getElementById('headerRow');
    if (!hr) return;
    
    // Limpiamos todo el contenido previo para evitar que se amontonen
    hr.innerHTML = ''; 

    const thCheck = document.createElement('th');
    thCheck.style.width = '40px';
    thCheck.innerHTML = `<input type="checkbox" onchange="toggleAllCheckboxes(this)">`;
    hr.appendChild(thCheck);

    window.COLUMN_DEFINITIONS.forEach(col => {
        const th = document.createElement('th');
        th.dataset.key = col.keyName;
        
        // Creamos la estructura limpia
        th.innerHTML = `
            <div class="th-content">
                ${escapeHtml(col.displayName)}
                <div class="sort-indicators">
                    <span class="tri-up" onclick="setSort('${col.keyName}','asc', event)">▲</span>
                    <span class="tri-down" onclick="setSort('${col.keyName}','desc', event)">▼</span>
                </div>
            </div>`;
        hr.appendChild(th);
    });
}

function toggleAllCheckboxes(master) {
    document.querySelectorAll('.row-selector').forEach(cb => cb.checked = master.checked);
}

async function deleteSelectedRows() {
    const selected = document.querySelectorAll('.row-selector:checked');
    if (selected.length === 0) {
        showToast('⚠️ Selecciona al menos una fila.');
        return;
    }
    const ids = Array.from(selected).map(cb => cb.dataset.id);
    if (!confirm(`¿Eliminar ${ids.length} fila(s)?`)) return;
    for (const id of ids) {
        await fetch(`/api/variables/${id}`, { method: 'DELETE' });
    }
    loadData();
    showToast(`✓ ${ids.length} fila(s) eliminada(s).`);
}

async function duplicateSelected() {
    const selected = document.querySelectorAll('.row-selector:checked');
    if (selected.length === 0) {
        showToast('⚠️ Selecciona al menos una fila para duplicar.');
        return;
    }
    const ids = Array.from(selected).map(cb => cb.dataset.id);
    let count = 0;
    for (const id of ids) {
        const r = await fetch(`/api/variables/${id}/duplicate`, { method: 'POST' });
        if (r.ok) count++;
    }
    loadData();
    showToast(`✓ ${count} fila(s) duplicada(s).`);
}

function renderTable() {
    const tbody = document.querySelector('#dataTable tbody');
    tbody.innerHTML = '';
    const totalPages = Math.ceil(filteredData.length / itemsPerPage) || 1;
    document.getElementById('totalPagesSpan').textContent = totalPages;
    document.getElementById('pageInput').value = currentPage;
    document.getElementById('prevPageBtnTable').disabled = currentPage <= 1;
    document.getElementById('nextPageBtnTable').disabled = currentPage >= totalPages;

    const start = (currentPage - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    const pageData = filteredData.slice(start, end);

    pageData.forEach(rowData => {
        const tr = document.createElement('tr');
        tr.dataset.id = rowData.id;

        const tdCheck = document.createElement('td');
        tdCheck.className = 'row-checkbox';
        tdCheck.style.textAlign = 'center';
        tdCheck.style.verticalAlign = 'middle';
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'row-selector';
        checkbox.dataset.id = rowData.id;
        tdCheck.appendChild(checkbox);
        tr.appendChild(tdCheck);

        window.COLUMN_DEFINITIONS.forEach(col => {
            const td = document.createElement('td');
            let val = rowData[col.keyName] !== undefined && rowData[col.keyName] !== null ? rowData[col.keyName] : '';
            if (col.keyName === 'valor' && val !== '') {
                val = formatNumero(val);
            }
            if (col.keyName === 'id') {
                td.innerHTML = `<input type="text" class="read-only-input" value="${escapeHtml(val)}" disabled style="width:auto;min-width:80px;">`;
            } else {
                const el = document.createElement(col.type === 'select' ? 'select' : 'textarea');
                el.className = 'edit-control';

                const placeholderMap = {
                    nombre: 'Insertar nombre',
                    liga_web: 'Insertar liga web',
                    fuente: 'Insertar fuente',
                    año: 'Insertar año',
                    valor: 'Insertar valor'
                };
                if (placeholderMap[col.keyName] && (!val || String(val).trim() === '')) {
                    el.placeholder = placeholderMap[col.keyName];
                }

                if (col.type === 'select') {
                    let htmlOpts = `<option value="">-seleccionar-</option>`;
                    (col.options || []).forEach(o => htmlOpts += `<option value="${escapeHtml(o)}" ${o===val?'selected':''}>${escapeHtml(o)}</option>`);
                    htmlOpts += `<option value="_OTRA_">Otra...</option>`;
                    el.innerHTML = htmlOpts;
                    el.onchange = async () => {
                        if (el.value === '_OTRA_') {
                            openOpcionesModal(col, rowData.id,
                                (newVal) => { rowData[col.keyName] = newVal; handleSearch(); },
                                () => { el.value = val; }
                            );
                        } else {
                            rowData[col.keyName] = el.value;
                            if (col.keyName === 'eje') updateTemaOptions(tr, el.value, rowData['tema']);
                            await saveRow(tr);
                            syncRowHeights(tr);
                        }
                    };
                    requestAnimationFrame(() => {
                        if (col.keyName === 'eje') updateTemaOptions(tr, val, rowData['tema']);
                    });
                } else {
                    el.value = val;
                    el.oninput = () => {
                        autoResize(el);
                        syncRowHeights(tr);
                    };
                    el.onchange = () => {
                        rowData[col.keyName] = el.value;
                        saveRow(tr);
                        syncRowHeights(tr);
                    };
                    requestAnimationFrame(() => autoResize(el));
                }
                td.appendChild(el);
            }
            tr.appendChild(td);
        });

        tbody.appendChild(tr);
        requestAnimationFrame(() => syncRowHeights(tr));
    });
}

async function saveRow(tr) {
    const id = tr.dataset.id;
    const data = {};
    const cells = tr.querySelectorAll('td');
    window.COLUMN_DEFINITIONS.forEach((col, idx) => {
        const ctrl = cells[idx + 1]?.querySelector('.edit-control');
        if (ctrl) data[col.keyName] = ctrl.value;
    });
    const resp = await fetch(`/api/variables/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (resp.ok) {
        showToast('✓ Celda actualizada');
        handleSearch();
    } else {
        showToast('Error al actualizar celda.');
    }
}

async function confirmAddRow() {
    const r = await fetch('/api/variables', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
    });
    if (r.ok) {
        const newRow = await r.json();
        originalData.unshift(newRow);
        handleSearch();
        showToast('✓ Fila creada');
    } else {
        const error = await r.json();
        showToast('Error: ' + (error.error || 'No se pudo crear la fila'));
        console.error('Error al crear fila:', error);
    }
}

function changeItemsPerPage(val) {
    itemsPerPage = parseInt(val);
    currentPage = 1;
    renderTable();
}

function goToPage(page) {
    const total = Math.ceil(filteredData.length / itemsPerPage) || 1;
    let p = parseInt(page);
    if (isNaN(p) || p < 1) p = 1;
    if (p > total) p = total;
    currentPage = p;
    renderTable();
}

function nextPage() {
    const total = Math.ceil(filteredData.length / itemsPerPage) || 1;
    if (currentPage < total) { currentPage++; renderTable(); }
}

function prevPage() {
    if (currentPage > 1) { currentPage--; renderTable(); }
}

function downloadCSV() {
    if (filteredData.length === 0) {
        showToast('No hay datos filtrados para descargar.');
        return;
    }
    const headers = window.COLUMN_DEFINITIONS.map(c => c.displayName);
    const rows = [headers.map(h => `"${h.replace(/"/g,'""')}"`).join(',')];
    filteredData.forEach(row => {
        const vals = window.COLUMN_DEFINITIONS.map(c => {
            let v = row[c.keyName] != null ? String(row[c.keyName]) : '';
            if (c.keyName === 'valor' && v !== '') {
                v = formatNumero(v);
            }
            return `"${v.replace(/"/g,'""')}"`;
        });
        rows.push(vals.join(','));
    });
    const csv = rows.join('\n');
    const blob = new Blob([new Uint8Array([0xEF,0xBB,0xBF]), csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const now = new Date();
    const fechaHora = now.getFullYear() +
                      String(now.getMonth() + 1).padStart(2, '0') +
                      String(now.getDate()).padStart(2, '0') +
                      String(now.getHours()).padStart(2, '0') +
                      String(now.getMinutes()).padStart(2, '0') +
                      String(now.getSeconds()).padStart(2, '0');
    a.download = `variables_${fechaHora}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('✓ CSV filtrado descargado');
}

// ============================================================
// PREVISUALIZACIÓN UNIFICADA (con logs de hashes)
// ============================================================
function renderPreviewTable(containerId, data, isZip = false) {
    const container = document.getElementById(containerId);
    if (!container) return;
    let html = '<table>';

    console.log(`🔍 Renderizando previsualización en ${containerId}: ${data.length} filas`);
    console.log('📊 Datos de previsualización:', data);

    if (data && data.length > 0) {
        const headerCols = window.COLUMN_DEFINITIONS.map(c => c.displayName);
        html += '<thead><tr>';
        html += '<th style="min-width:80px;">Acción</th>';
        headerCols.forEach(k => {
            html += `<th>${escapeHtml(k)}</th>`;
        });
        html += '</tr></thead>';

        const maxRows = Math.min(data.length, 20);
        html += '<tbody>';
        for (let i = 0; i < maxRows; i++) {
            const rowInfo = data[i];
            const rowData = rowInfo.data || rowInfo;
            const isDup = rowInfo._is_duplicate || false;
            const cls = isDup ? 'duplicate-row-preview' : '';
            const checked = isDup && rowInfo._action === 'overwrite' ? 'checked' : '';

            if (rowInfo._hash) {
                console.log(`Fila ${i} hash: ${rowInfo._hash} ${isDup ? '🔴 DUPLICADO' : '🟢 NUEVO'}`);
            }

            let actionHtml = isDup
                ? `<td><input type="checkbox" class="action-checkbox" data-index="${i}" data-iszip="${isZip}" ${checked}> Sobrescribir</td>`
                : '<td style="text-align:center;color:#28a745;font-weight:500;">✓ Insertar</td>';

            const rowSeg = window.COLUMN_DEFINITIONS.map(col => {
                let val = rowData[col.keyName] !== undefined && rowData[col.keyName] !== null ? String(rowData[col.keyName]) : '';
                if (col.keyName === 'valor' && val !== '' && !isNaN(val)) {
                    val = formatNumero(val);
                }
                let inputHtml = '';
                if (col.type === 'select' && col.keyName !== 'id') {
                    let opts = `<option value="">-seleccionar-</option>`;
                    (col.options || []).forEach(o => opts += `<option value="${escapeHtml(o)}" ${o===val?'selected':''}>${escapeHtml(o)}</option>`);
                    opts += `<option value="_OTRA_">Otra...</option>`;
                    inputHtml = `<select class="preview-edit" data-col="${col.keyName}" data-index="${i}" data-iszip="${isZip}">${opts}</select>`;
                } else if (col.keyName === 'id') {
                    inputHtml = `<span style="font-weight:600;color:#2d3748;">${escapeHtml(val)}</span>`;
                } else {
                    inputHtml = `<input type="text" class="preview-edit" data-col="${col.keyName}" data-index="${i}" data-iszip="${isZip}" value="${escapeHtml(val)}">`;
                }
                return `<td>${inputHtml}</td>`;
            }).join('');

            html += `<tr class="${cls}">${actionHtml}${rowSeg}</tr>`;
        }
        if (data.length > 20) {
            html += `<tr><td colspan="${window.COLUMN_DEFINITIONS.length + 1}" style="padding:8px;text-align:center;font-style:italic;background:#f8f9fa;">... y ${data.length - 20} filas más</td></tr>`;
        }
        html += '</tbody>';
    } else {
        html += '<tbody><tr><td colspan="14" style="padding:8px;text-align:center;color:#6c757d;">No hay datos para previsualizar.</td></tr></tbody>';
    }

    html += '</table>';
    container.innerHTML = html;

    // Eventos para edición
    document.querySelectorAll(`#${containerId} .preview-edit`).forEach(el => {
        el.addEventListener('change', function() {
            const idx = parseInt(this.dataset.index);
            const col = this.dataset.col;
            const isZip = this.dataset.iszip === 'true';
            let targetData = isZip ? folderPreviewData : allPreviewData;
            if (targetData[idx]) {
                if (this.tagName === 'SELECT' && this.value === '_OTRA_') {
                    const colDef = window.COLUMN_DEFINITIONS.find(c => c.keyName === col);
                    if (colDef) {
                        const rowId = targetData[idx].data?.id || 'new';
                        openOpcionesModal(colDef, rowId,
                            (newVal) => {
                                targetData[idx].data[col] = newVal;
                                renderPreviewTable(containerId, targetData, isZip);
                            },
                            () => { /* cancelar */ }
                        );
                    }
                } else {
                    targetData[idx].data[col] = this.value;
                }
            }
        });
    });

    // Checkboxes para duplicados
    document.querySelectorAll(`#${containerId} .action-checkbox`).forEach(cb => {
        cb.addEventListener('change', function() {
            const idx = parseInt(this.dataset.index);
            const isZip = this.dataset.iszip === 'true';
            let targetData = isZip ? folderPreviewData : allPreviewData;
            if (targetData[idx]) {
                targetData[idx]._action = this.checked ? 'overwrite' : 'ignore';
                updateSelectAllCheckbox(containerId, isZip);
            }
        });
    });

    updateSelectAllCheckbox(containerId, isZip);
}

function updateSelectAllCheckbox(containerId, isZip) {
    const container = document.getElementById(containerId);
    if (!container) return;
    let targetData = isZip ? folderPreviewData : allPreviewData;
    const dups = targetData.filter(r => r._is_duplicate);
    const selAllId = isZip ? 'selectAllDuplicatesForOverwriteZip' : 'selectAllDuplicatesForOverwrite';
    const selAll = document.getElementById(selAllId);
    if (selAll) {
        selAll.checked = dups.every(r => r._action === 'overwrite');
        selAll.onchange = () => {
            targetData.forEach(r => { if (r._is_duplicate) r._action = selAll.checked ? 'overwrite' : 'ignore'; });
            renderPreviewTable(containerId, targetData, isZip);
        };
    }
}

// --- Importar CSV con barra de progreso ---
async function handleFileUpload(input) {
    const file = input.files[0];
    if (!file) return;
    if (!file.name.endsWith('.csv')) {
        showToast('⚠️ Por favor, sube un archivo CSV.');
        input.value = '';
        return;
    }
    currentFileToUpload = file;
    document.getElementById('uploadFileName').textContent = file.name;
    document.getElementById('uploadPreviewMessages').innerHTML = '';
    document.getElementById('uploadDataPreview').innerHTML = '';
    const progressDiv = document.getElementById('uploadProgress');
    const progressFill = document.getElementById('uploadProgressFill');
    const progressText = document.getElementById('uploadProgressText');
    progressDiv.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = 'Subiendo archivo...';

    openModal('modalConfirmUpload');

    const fd = new FormData();
    fd.append('file', file);
    try {
        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 15;
            if (progress > 90) progress = 90;
            progressFill.style.width = progress + '%';
            progressText.textContent = `Procesando... ${Math.round(progress)}%`;
        }, 300);

        const r = await fetch('/api/upload?preview=true', { method: 'POST', body: fd });
        clearInterval(interval);
        progressFill.style.width = '100%';
        progressText.textContent = '¡Completado!';
        setTimeout(() => { progressDiv.style.display = 'none'; }, 1000);

        if (r.ok) {
            const data = await r.json();
            document.getElementById('uploadPreviewMessages').innerHTML = data.messages.map(m => `<div>${escapeHtml(m)}</div>`).join('');
            allPreviewData = data.preview_data || [];
            console.log(`📥 Datos recibidos del backend (${allPreviewData.length} filas):`, allPreviewData);
            allPreviewData.forEach(row => { row._action = row._is_duplicate ? 'ignore' : 'insert'; });
            previewCurrentPage = 0;
            renderPreviewTable('uploadDataPreview', allPreviewData, false);
        } else {
            const err = await r.json();
            document.getElementById('uploadPreviewMessages').innerHTML = `<div style="color:var(--sort-active);">Error: ${err.error || 'Algo salió mal'}</div>`;
            allPreviewData = [];
        }
    } catch (e) {
        document.getElementById('uploadPreviewMessages').innerHTML = `<div style="color:var(--sort-active);">Error de conexión: ${e.message}</div>`;
        allPreviewData = [];
    }
}

async function confirmUpload() {
    closeModal('modalConfirmUpload');
    if (!currentFileToUpload) return showToast('Error: No hay archivo para cargar.');

    const actions = allPreviewData.map(row => ({
        original_csv_index: row.original_csv_index,
        action: row._action,
        data: row.data,
        _is_duplicate: row._is_duplicate,
        _supabase_matching_id: row._supabase_matching_id
    }));

    console.log("%c 🚀 Enviando al backend (CSV): ", "background: #222; color: #ffaa00; font-size: 14px;", actions);

    const fd = new FormData();
    fd.append('file', currentFileToUpload);
    fd.append('actions_for_rows', JSON.stringify(actions));

    const r = await fetch('/api/upload', { method: 'POST', body: fd });
    const data = await r.json();

    if (data.debug) {
        console.log("%c 📡 Logs del backend (CSV): ", "background: #222; color: #00ffaa; font-size: 14px;", data.debug);
    }

    if (r.ok) {
        showToast(data.message);
        await loadData();
        loadHistory();
    } else {
        showToast(`Error: ${data.error || 'Algo salió mal'}`);
    }
    currentFileToUpload = null;
}

// --- Carga de carpeta ZIP (con barra de progreso) ---
async function handleZipUpload(input) {
    const file = input.files[0];
    if (!file) return;
    if (!file.name.endsWith('.zip')) {
        showToast('⚠️ Por favor, selecciona un archivo ZIP.');
        input.value = '';
        return;
    }

    const previewContainer = document.getElementById('zipPreviewContainer');
    const logContainer = document.getElementById('folderLogMessages');
    const logContent = document.getElementById('folderLogContent');
    const progressDiv = document.getElementById('zipProgress');
    const progressFill = document.getElementById('zipProgressFill');
    const progressText = document.getElementById('zipProgressText');

    if (previewContainer) previewContainer.style.display = 'none';
    if (logContainer) logContainer.style.display = 'none';

    if (progressDiv) {
        progressDiv.style.display = 'block';
        progressFill.style.width = '0%';
        progressText.textContent = 'Subiendo archivo...';
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 15;
            if (progress > 90) progress = 90;
            progressFill.style.width = progress + '%';
            progressText.textContent = `Procesando... ${Math.round(progress)}%`;
        }, 300);

        const response = await fetch('/api/process-folder', {
            method: 'POST',
            body: formData
        });

        clearInterval(interval);
        progressFill.style.width = '100%';
        progressText.textContent = '¡Completado!';

        if (response.ok) {
            const data = await response.json();
            folderPreviewData = data.preview_data || [];
            console.log(`📥 Datos ZIP recibidos (${folderPreviewData.length} filas):`, folderPreviewData);
            folderPreviewData.forEach(row => {
                if (row._is_duplicate === undefined) row._is_duplicate = false;
                if (row._action === undefined) row._action = row._is_duplicate ? 'ignore' : 'insert';
            });
            folderGlobalMetadata = data.global_metadata || {};
            currentZipFilename = data.zip_filename || file.name;

            if (logContainer && logContent) {
                if (data.messages && data.messages.length > 0) {
                    logContainer.style.display = 'block';
                    logContent.innerHTML = data.messages.map(m => escapeHtml(m)).join('<br>');
                } else {
                    logContainer.style.display = 'none';
                }
            }

            if (previewContainer) {
                previewContainer.style.display = 'block';
                renderPreviewTable('zipPreviewTable', folderPreviewData, true);
                document.getElementById('rowCount').textContent = folderPreviewData.length;
            }
            showToast(`✓ Procesamiento completado: ${folderPreviewData.length} filas extraídas.`);
        } else {
            const error = await response.json();
            showToast('Error: ' + (error.error || 'Algo salió mal'));
            if (logContainer && logContent) {
                logContainer.style.display = 'block';
                const errorMsg = escapeHtml(error.error || 'Error desconocido');
                const tracebackMsg = error.traceback ? '<br>' + escapeHtml(error.traceback) : '';
                logContent.innerHTML = errorMsg + tracebackMsg;
            }
        }
    } catch (e) {
        showToast('Error de conexión: ' + e.message);
    } finally {
        setTimeout(() => {
            if (progressDiv) progressDiv.style.display = 'none';
        }, 1000);
    }
}

async function confirmFolderUpload() {
    if (!folderPreviewData || folderPreviewData.length === 0) {
        showToast('No hay datos para cargar.');
        return;
    }

    const actions = folderPreviewData.map((row, index) => ({
        original_csv_index: index,
        action: row._action || (row._is_duplicate ? 'ignore' : 'insert'),
        data: row.data || row,
        _is_duplicate: row._is_duplicate || false,
        _supabase_matching_id: row._supabase_matching_id || null
    }));

    console.log("%c 🚀 Enviando al backend (ZIP): ", "background: #222; color: #ffaa00; font-size: 14px;", actions);

    const fd = new FormData();
    fd.append('actions_for_rows', JSON.stringify(actions));
    fd.append('zip_filename', currentZipFilename || 'carga_carpeta');

    try {
        const response = await fetch('/api/confirm-folder', {
            method: 'POST',
            body: fd
        });
        const data = await response.json();

        if (data.debug) {
            console.log("%c 📡 Logs del backend (ZIP): ", "background: #222; color: #00ffaa; font-size: 14px;", data.debug);
        }

        if (response.ok) {
            showToast(data.message || '✓ Carga completada');
            await loadData();
            loadHistory();
            closeModal('modalFolderUpload');
            resetFolderModal();
        } else {
            showToast('Error: ' + (data.error || 'Algo salió mal'));
        }
    } catch (e) {
        showToast('Error de conexión: ' + e.message);
    }
}

async function loadHistory() {
    try {
        const r = await fetch('/api/upload-history');
        if (r.ok) {
            const history = await r.json();
            const container = document.getElementById('historyList');
            if (history.length === 0) {
                container.innerHTML = '<p style="color:var(--text-muted);">No hay cargas registradas.</p>';
                return;
            }
            let html = `<table>
                <thead><tr><th>Fecha</th><th>Archivo</th><th>Filas</th><th>Estado</th></tr></thead><tbody>`;
            history.forEach(item => {
                let fechaFormateada = '';
                if (item.fecha) {
                    try {
                        const date = new Date(item.fecha);
                        if (!isNaN(date.getTime())) {
                            const dia = String(date.getDate()).padStart(2, '0');
                            const mes = String(date.getMonth() + 1).padStart(2, '0');
                            const año = date.getFullYear();
                            const horas = String(date.getHours()).padStart(2, '0');
                            const minutos = String(date.getMinutes()).padStart(2, '0');
                            const segundos = String(date.getSeconds()).padStart(2, '0');
                            fechaFormateada = `${dia}/${mes}/${año} ${horas}:${minutos}:${segundos}`;
                        } else {
                            fechaFormateada = item.fecha;
                        }
                    } catch {
                        fechaFormateada = item.fecha;
                    }
                }
                const statusClass = item.estado === 'completado' ? 'status-success' :
                                  item.estado === 'error' ? 'status-error' : 'status-pending';
                html += `<tr>
                    <td>${escapeHtml(fechaFormateada)}</td>
                    <td>${escapeHtml(item.archivo || '')}</td>
                    <td>${escapeHtml(item.filas_agregadas || '')}</td>
                    <td class="${statusClass}">${escapeHtml(item.estado || '')}</td>
                </tr>`;
            });
            html += '</tbody></table>';
            container.innerHTML = html;
        }
    } catch (e) {
        console.warn('Error al cargar historial:', e);
    }
}

async function retrainModels() {
    const btn = document.querySelector('button[onclick="retrainModels()"]');
    if (!btn) return;
    btn.disabled = true;
    btn.textContent = '⏳ Entrenando...';
    showToast('⏳ Entrenando modelos, esto puede tomar unos segundos...');

    try {
        const r = await fetch('/api/retrain-models', { method: 'POST' });
        const data = await r.json();
        if (r.ok) {
            let msg = '✅ ' + data.message;
            if (data.report) {
                const p = data.report.proceso || {};
                const e = data.report.eje || {};
                const t = data.report.tema || {};
                const precision = `P:${(p.accuracy*100||0).toFixed(1)}% | E:${(e.accuracy*100||0).toFixed(1)}% | T:${(t.accuracy*100||0).toFixed(1)}%`;
                msg += ` (${precision})`;
                if (p.accuracy < 0.7 || e.accuracy < 0.7 || t.accuracy < 0.7) {
                    msg += ' ⚠️ Precisión baja. Considera revisar datos.';
                }
            }
            showToast(msg);
        } else {
            showToast('❌ Error: ' + (data.error || 'Algo salió mal'));
        }
    } catch (e) {
        showToast('❌ Error de conexión: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '🔄 Reentrenar Modelos';
    }
}

async function rollbackModels() {
    if (!confirm('⚠️ ¿Restaurar los modelos a la versión anterior? Se perderán los cambios del último reentrenamiento.')) return;
    const r = await fetch('/api/rollback-models', { method: 'POST' });
    const data = await r.json();
    if (r.ok) {
        showToast('✅ ' + data.message);
    } else {
        showToast('❌ ' + (data.error || 'No hay backup disponible'));
    }
}

const dropZone = document.getElementById('dropZone');
if (dropZone) {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {
        dropZone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); }, false);
    });
    dropZone.addEventListener('dragenter', () => dropZone.classList.add('drag-over'), false);
    dropZone.addEventListener('dragover', () => dropZone.classList.add('drag-over'), false);
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'), false);
    dropZone.addEventListener('drop', e => {
        dropZone.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (file) {
            if (file.name.endsWith('.csv')) {
                handleFileUpload({ files: [file] });
            } else if (file.name.endsWith('.zip')) {
                openModal('modalFolderUpload');
                const input = document.getElementById('zipFileInput');
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                input.files = dataTransfer.files;
                const event = new Event('change', { bubbles: true });
                input.dispatchEvent(event);
            } else {
                showToast('⚠️ Solo se permiten archivos CSV o ZIP.');
            }
        }
    }, false);
} else {
    console.warn('Elemento #dropZone no encontrado.');
}

window.onload = async () => {
    await loadData();
    renderHeaders();
    document.getElementById('itemsPerPageSelect').value = itemsPerPage;
    await loadHistory();

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            if (document.getElementById('modalOtraOpcion').style.display === 'flex') handleCloseOtraOpcionModal();
            else if (document.getElementById('modalSuggestion').style.display === 'flex') {
                const btn = document.getElementById('btnDeclineSuggestion');
                if (btn) btn.click();
                closeModal('modalSuggestion');
            } else if (document.getElementById('modalConfirmUpload').style.display === 'flex') {
                closeModal('modalConfirmUpload');
            } else if (document.getElementById('modalFolderUpload').style.display === 'flex') {
                closeModal('modalFolderUpload');
            }
        }
    });
};