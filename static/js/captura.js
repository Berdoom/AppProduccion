// static/js/captura.js
document.addEventListener('DOMContentLoaded', () => {
    // Variable para rastrear si hay cambios sin guardar en el formulario.
    let hasUnsavedChanges = false;
    const productionForm = document.getElementById('productionForm');

    if (productionForm) {
        // Cuando el usuario escribe en cualquier campo, marcar que hay cambios.
        productionForm.addEventListener('input', () => { hasUnsavedChanges = true; });
        // Cuando el formulario se envía, resetear la bandera de cambios.
        productionForm.addEventListener('submit', () => { hasUnsavedChanges = false; });
    }

    // Advertir al usuario si intenta salir de la página con cambios sin guardar.
    window.addEventListener('beforeunload', (e) => {
        if (hasUnsavedChanges) {
            e.preventDefault(); // Requerido por algunos navegadores.
            e.returnValue = ''; // Muestra un diálogo de confirmación genérico.
        }
    });

    // Si las variables de áreas existen (pasadas desde Flask), calcular los totales iniciales.
    if (typeof AREAS_JS !== 'undefined') {
        AREAS_JS.forEach(area => {
            calculateTotals(toSlug(area));
        });
    }
});

/**
 * Convierte un texto a un formato 'slug' (ej. "Turno A" -> "Turno_A").
 * @param {string} text - El texto a convertir.
 * @returns {string} El texto en formato slug.
 */
function toSlug(text) {
    return text.replace(/ /g, '_').replace(/\./g, '').replace(/\//g, '');
}

/**
 * (VERSIÓN MEJORADA) Recarga la página con la fecha seleccionada.
 * Esta función ahora construye la URL de forma segura usando el 'data-group' del formulario.
 */
function handleDateChange() {
    const form = document.getElementById('productionForm');
    const group = form.dataset.group; // Obtiene el grupo (ej: "IHP" o "FHP")
    const fecha = document.getElementById('fecha').value;

    // Verificación para asegurar que el grupo está definido.
    if (!group) {
        console.error("Error: El atributo 'data-group' no está definido en el formulario.");
        alert("Error crítico: No se puede cambiar la fecha porque el grupo de producción no está definido.");
        return;
    }

    // Construye la URL correctamente. Ej: /captura/ihp?fecha=2025-06-26
    const newUrl = `/captura/${group.toLowerCase()}?fecha=${fecha}`;
    
    // Redirige a la nueva URL.
    window.location.href = newUrl;
}

/**
 * Calcula y actualiza los totales de pronóstico y producción para un área específica.
 * @param {string} areaSlug - El slug del área a calcular.
 */
function calculateTotals(areaSlug) {
    let totalPronosticoArea = 0;
    let totalProduccionArea = 0;

    // Iterar sobre cada turno definido en las variables de JS.
    NOMBRES_TURNOS_JS.forEach(turnoName => {
        const turnoSlug = toSlug(turnoName);
        const pronosticoTurnoInput = document.querySelector(`input[name="pronostico_${areaSlug}_${turnoSlug}"]`);
        if (pronosticoTurnoInput) {
            totalPronosticoArea += parseInt(pronosticoTurnoInput.value) || 0;
        }
        
        let totalProduccionTurno = 0;
        // Iterar sobre las horas de cada turno.
        HORAS_TURNO_JS[turnoName].forEach(hora => {
            const produccionInput = document.querySelector(`input[name="produccion_${areaSlug}_${hora}"]`);
            if (produccionInput) {
                totalProduccionTurno += parseInt(produccionInput.value) || 0;
            }
        });
        
        // Actualizar el span que muestra el total del turno.
        const totalTurnoSpan = document.getElementById(`total_produccion_turno_${areaSlug}_${turnoSlug}`);
        if (totalTurnoSpan) {
            totalTurnoSpan.innerText = totalProduccionTurno;
        }
        totalProduccionArea += totalProduccionTurno;
    });

    // Actualizar el span del pronóstico total del área.
    const totalPronosticoSpan = document.getElementById(`total_pronostico_area_${areaSlug}`);
    if (totalPronosticoSpan) {
        totalPronosticoSpan.innerText = totalPronosticoArea;
    }

    // Actualizar el span de la producción total del área.
    const totalProduccionSpan = document.getElementById(`total_produccion_area_${areaSlug}`);
    if (totalProduccionSpan) {
        totalProduccionSpan.innerText = totalProduccionArea;
    }
}

/**
 * Prepara el modal para registrar una razón, poblando los campos con los datos del botón que lo activó.
 * @param {HTMLElement} button - El botón que disparó el evento.
 */
function setReasonModalData(button) {
    document.getElementById('modalAreaName').innerText = button.dataset.areaName;
    document.getElementById('modalTurnoName').innerText = button.dataset.turnoName;
    document.getElementById('modalDate').value = button.dataset.date;
    document.getElementById('modalArea').value = button.dataset.areaName;
    document.getElementById('modalTurno').value = button.dataset.turnoName;
    document.getElementById('reasonText').value = ''; // Limpiar el textarea.
}

/**
 * Muestra un modal de feedback (éxito o error).
 * @param {string} title - El título del modal.
 * @param {string} message - El mensaje a mostrar.
 * @param {boolean} isSuccess - Si es un mensaje de éxito (verde) o error (rojo).
 */
function showFeedback(title, message, isSuccess) {
    const header = document.getElementById('feedbackModalHeader');
    document.getElementById('feedbackModalLabel').innerText = title;
    document.getElementById('feedbackModalBody').innerText = message;
    header.className = isSuccess ? 'modal-header bg-success text-white' : 'modal-header bg-danger text-white';
    $('#feedbackModal').modal('show');
}

/**
 * Envía la razón de desviación al servidor mediante una petición AJAX.
 */
function submitReason() {
    const reasonText = document.getElementById('reasonText').value;
    if (!reasonText.trim()) {
        showFeedback('Error de Validación', 'La razón no puede estar vacía.', false);
        return;
    }

    $('#reasonModal').modal('hide');
    
    const form = document.getElementById('productionForm');
    const submitUrl = form.dataset.submitReasonUrl;
    const csrfToken = document.querySelector('input[name="csrf_token"]').value;
    const group = form.dataset.group;

    // Usamos jQuery.ajax para enviar los datos.
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
            if (response.status === 'success') {
                showFeedback('Éxito', response.message, true);
                // Cuando se cierra el modal de éxito, recargar la página para ver el cambio.
                $('#feedbackModal').on('hidden.bs.modal', () => location.reload());
            } else {
                showFeedback('Error al Guardar', response.message || 'Ocurrió un error desconocido.', false);
            }
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.error("Error en AJAX:", textStatus, errorThrown, jqXHR.responseText);
            showFeedback('Error de Conexión', 'No se pudo comunicar con el servidor. Revisa la consola para más detalles.', false);
        }
    });
}
