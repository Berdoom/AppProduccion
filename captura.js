// static/js/captura.js (Versión Responsiva)

document.addEventListener('DOMContentLoaded', () => {
    let hasUnsavedChanges = false;
    const productionForm = document.getElementById('productionForm');

    if (productionForm) {
        productionForm.addEventListener('input', () => { hasUnsavedChanges = true; });
        productionForm.addEventListener('submit', () => { hasUnsavedChanges = false; });
    }

    window.addEventListener('beforeunload', (e) => {
        if (hasUnsavedChanges) {
            e.preventDefault();
            e.returnValue = '';
        }
    });

    // Calcular totales para todas las áreas al cargar la página
    if (typeof AREAS_JS !== 'undefined') {
        AREAS_JS.forEach(area => {
            calculateTotals(toSlug(area));
        });
    }

    // Manejar la rotación del ícono de flecha en el acordeón
    $('.collapse').on('shown.bs.collapse', function () {
        $(this).prev('.area-card-header').find('.arrow-icon').css('transform', 'rotate(0deg)');
    });
    $('.collapse').on('hidden.bs.collapse', function () {
        $(this).prev('.area-card-header').find('.arrow-icon').css('transform', 'rotate(-90deg)');
    });
});

function toSlug(text) {
    return text.replace(/ /g, '_').replace(/\./g, '').replace(/\//g, '');
}

function handleDateChange() {
    const form = document.getElementById('productionForm');
    const group = form.dataset.group;
    const fecha = document.getElementById('fecha').value;

    if (!group) {
        console.error("Error: El atributo 'data-group' no está definido en el formulario.");
        return;
    }
    window.location.href = `/captura/${group.toLowerCase()}?fecha=${fecha}`;
}

/**
 * Calcula y actualiza los totales para un área específica, adaptado a la estructura de tarjetas.
 * @param {string} areaSlug - El slug del área a calcular.
 */
function calculateTotals(areaSlug) {
    const areaCard = document.querySelector(`.area-card[data-area-slug="${areaSlug}"]`);
    if (!areaCard) return;

    let totalPronosticoArea = 0;
    let totalProduccionArea = 0;

    NOMBRES_TURNOS_JS.forEach(turnoName => {
        const turnoSlug = toSlug(turnoName);
        const pronosticoTurnoInput = areaCard.querySelector(`input[name="pronostico_${areaSlug}_${turnoSlug}"]`);
        if (pronosticoTurnoInput) {
            totalPronosticoArea += parseInt(pronosticoTurnoInput.value) || 0;
        }
        
        let totalProduccionTurno = 0;
        HORAS_TURNO_JS[turnoName].forEach(hora => {
            const produccionInput = areaCard.querySelector(`input[name="produccion_${areaSlug}_${hora}"]`);
            if (produccionInput) {
                totalProduccionTurno += parseInt(produccionInput.value) || 0;
            }
        });
        
        const totalTurnoSpan = areaCard.querySelector(`#total_produccion_turno_${areaSlug}_${turnoSlug}`);
        if (totalTurnoSpan) {
            totalTurnoSpan.innerText = totalProduccionTurno;
        }
        totalProduccionArea += totalProduccionTurno;
    });

    const totalPronosticoSpan = areaCard.querySelector(`#total_pronostico_area_${areaSlug}`);
    if (totalPronosticoSpan) {
        totalPronosticoSpan.innerText = totalPronosticoArea;
    }

    const totalProduccionSpan = areaCard.querySelector(`#total_produccion_area_${areaSlug}`);
    if (totalProduccionSpan) {
        totalProduccionSpan.innerText = totalProduccionArea;
    }
}

// Las funciones setReasonModalData y submitReason no necesitan cambios.
// (Se omiten por brevedad, son idénticas a la versión anterior)
function setReasonModalData(button) {
    document.getElementById('modalAreaName').innerText = button.dataset.areaName;
    document.getElementById('modalTurnoName').innerText = button.dataset.turnoName;
    document.getElementById('modalDate').value = button.dataset.date;
    document.getElementById('modalArea').value = button.dataset.areaName;
    document.getElementById('modalTurno').value = button.dataset.turnoName;
    document.getElementById('reasonText').value = '';
}

function submitReason() {
    const reasonText = document.getElementById('reasonText').value;
    if (!reasonText.trim()) {
        alert('La razón no puede estar vacía.');
        return;
    }

    $('#reasonModal').modal('hide');
    
    const form = document.getElementById('productionForm');
    const submitUrl = form.dataset.submitReasonUrl;
    const csrfToken = document.querySelector('input[name="csrf_token"]').value;
    const group = form.dataset.group;

    $.ajax({
        url: submitUrl,
        type: "POST",
        data: {
            csrf_token: csrfToken,
            date: document.getElementById('modalDate').value,
            area: document.getElementById('modalArea').value,
            group: group,
            reason: reasonText,
            turno_name: document.getElementById('modalTurno').value
        },
        success: function(response) {
            alert(response.message);
            if (response.status === 'success') {
                location.reload();
            }
        },
        error: function() {
            alert('Error de conexión. No se pudo guardar la razón.');
        }
    });
}
