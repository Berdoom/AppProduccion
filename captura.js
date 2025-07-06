document.addEventListener('DOMContentLoaded', () => {
    // --- Lógica para la vista de Escritorio ---
    if (document.querySelector('.desktop-view')) {
        FLASK_DATA.areas.forEach(area => {
            calculateDesktopTotals(toSlug(area));
        });
        // Recalcular al cambiar cualquier valor
        document.querySelector('.desktop-view').addEventListener('input', (e) => {
            if (e.target.matches('input[type="number"]')) {
                const areaRow = e.target.closest('tr');
                if (areaRow) {
                    calculateDesktopTotals(areaRow.dataset.areaSlug);
                }
            }
        });
    }

    // --- Lógica para la nueva vista Móvil ---
    const areaList = document.getElementById('mobile-area-list');
    const detailView = document.getElementById('mobile-detail-view');

    if (areaList && detailView) {
        // Evento para mostrar el detalle de un área
        areaList.addEventListener('click', (e) => {
            e.preventDefault();
            const target = e.target.closest('.mobile-area-item');
            if (target) {
                const areaSlug = target.dataset.areaSlug;
                const areaName = target.dataset.areaName;
                showAreaDetail(areaSlug, areaName);
            }
        });

        // Evento para volver a la lista de áreas
        document.getElementById('back-to-list-btn').addEventListener('click', () => {
            showAreaList();
        });
    }
});

function toSlug(text) {
    return text.replace(/ /g, '_').replace(/\./g, '').replace(/\//g, '');
}

function handleDateChange() {
    const fecha = document.getElementById('fecha').value;
    const group = document.getElementById('productionForm').dataset.group;
    window.location.href = `/captura/${group.toLowerCase()}?fecha=${fecha}`;
}

// --- Funciones para la Vista de Escritorio ---
function calculateDesktopTotals(areaSlug) {
    let totalProduccionArea = 0;
    const areaRow = document.querySelector(`.desktop-view tr[data-area-slug="${areaSlug}"]`);
    if (!areaRow) return;

    const inputs = areaRow.querySelectorAll('input[name^="produccion_"]');
    inputs.forEach(input => {
        totalProduccionArea += parseInt(input.value) || 0;
    });

    const totalSpan = areaRow.querySelector(`#total_produccion_area_${areaSlug}`);
    if (totalSpan) {
        totalSpan.innerText = totalProduccionArea;
    }
}

// --- Funciones para la Vista Móvil ---
function showAreaList() {
    document.getElementById('mobile-area-list').style.display = 'block';
    document.getElementById('mobile-detail-view').style.display = 'none';
}

function showAreaDetail(areaSlug, areaName) {
    document.getElementById('mobile-area-list').style.display = 'none';
    document.getElementById('mobile-detail-view').style.display = 'block';
    document.getElementById('detail-area-name').innerText = areaName;

    const formContent = document.getElementById('detail-form-content');
    formContent.innerHTML = ''; // Limpiar contenido anterior

    FLASK_DATA.nombres_turnos.forEach(turnoName => {
        const turnoSlug = toSlug(turnoName);
        const turnoSection = document.createElement('div');
        turnoSection.className = 'turno-section-mobile';
        
        let turnoHTML = `<h5 class="turno-title-mobile">${turnoName}</h5>`;

        // Input de Pronóstico
        const pronosticoName = `pronostico_${areaSlug}_${turnoSlug}`;
        const pronosticoValue = FLASK_DATA.initial_data[areaName]?.[`Pronostico_${turnoSlug}`] || '';
        turnoHTML += `
            <div class="form-group">
                <label>Pronóstico</label>
                <input type="number" name="${pronosticoName}" value="${pronosticoValue}" min="0" class="form-control pronostico-input">
            </div>
        `;

        // Inputs de Producción por hora
        FLASK_DATA.horas_turno[turnoName].forEach(hora => {
            const produccionName = `produccion_${areaSlug}_${hora}`;
            const produccionValue = FLASK_DATA.initial_data[areaName]?.[`Produccion_${hora}`] || '';
            turnoHTML += `
                <div class="form-group">
                    <label>Producción ${hora}</label>
                    <input type="number" name="${produccionName}" value="${produccionValue}" min="0" class="form-control">
                </div>
            `;
        });

        turnoSection.innerHTML = turnoHTML;
        formContent.appendChild(turnoSection);
    });
}
