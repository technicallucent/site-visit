// Mobile Verification & Auto-Fill Logic
document.addEventListener('DOMContentLoaded', function () {
    // Set default visit date to today
    const today = new Date().toISOString().split('T')[0];
    document.querySelector('.visit-date').value = today;

    // Load locations on page load
    loadLocations();
});

document.getElementById('verifyMobile').addEventListener('click', function () {
    const mobile = document.getElementById('mobileNumber').value.trim();

    if (!mobile || mobile.length !== 10 || !/^\d+$/.test(mobile)) {
        alert('Please enter a valid 10-digit mobile number');
        return;
    }

    const verifyBtn = this;
    verifyBtn.disabled = true;
    verifyBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Verifying...';

    const formData = new URLSearchParams();
    formData.append('mobile', mobile);

    fetch('/log-visit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData
    })
        .then(response => {
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            return response.json();
        })
        .then(data => {
            const clientSection = document.getElementById('clientDataSection');
            const previousVisitsCard = document.getElementById('previousVisitsCard');
            const previousVisitsList = document.getElementById('previousVisitsList');

            clientSection.style.display = 'block';
            document.querySelector('input[name="mobile"]').value = mobile;

            // Ensure locations are loaded before filling client form
            loadLocations().then(() => {
                if (data.exists) {
                    fillClientForm(data.client);

                    // Show previous visits
                    if (data.previous_visits && data.previous_visits.length > 0) {
                        previousVisitsCard.style.display = 'block';
                        previousVisitsList.innerHTML = data.previous_visits.map(visit => `
                        <div class="alert alert-info mb-2">
                            <strong>${visit.date}</strong> - ${visit.project} (${visit.status})
                            ${visit.agents ? `<br><small>Agents: ${visit.agents}</small>` : ''}
                        </div>
                    `).join('');
                    } else {
                        previousVisitsCard.style.display = 'none';
                        previousVisitsList.innerHTML = '';
                    }
                } else {
                    // New client: clear form (except mobile)
                    previousVisitsCard.style.display = 'none';
                    previousVisitsList.innerHTML = '';
                    document.getElementById('visitsForm').reset();
                    document.querySelector('input[name="mobile"]').value = mobile;
                    $('.select2').val(null).trigger('change');
                }
            });

            clientSection.scrollIntoView({ behavior: 'smooth' });
        })
        .catch(error => console.error('Verification error:', error))
        .finally(() => {
            verifyBtn.disabled = false;
            verifyBtn.innerHTML = '<i class="fas fa-check me-1"></i>Verify';
        });
});

function fillClientForm(client) {
    document.querySelector('input[name="name"]').value = client.name || '';
    document.querySelector('input[name="email"]').value = client.email || '';
    document.querySelector('input[name="secondary_number"]').value = client.secondary_number || '';

    // Current Location (single select)
    
    if (client.current_location) {
        $('select[name="current_location"]').val(client.current_location).trigger('change');
    } else {
        $('select[name="current_location"]').val(null).trigger('change');
    }

    document.querySelector('input[name="building_name"]').value = client.building_name || '';
    document.querySelector('textarea[name="notes"]').value = client.notes || '';

    // Simple select fields
    if (client.profession) $('select[name="profession"]').val(client.profession).trigger('change');
    if (client.lead_source_project) $('select[name="lead_source_project"]').val(client.lead_source_project).trigger('change');
    if (client.lead_source) $('select[name="lead_source"]').val(client.lead_source).trigger('change');
    if (client.bhk_requirement) $('select[name="bhk_requirement"]').val(client.bhk_requirement).trigger('change');
    if (client.budget) $('select[name="budget"]').val(client.budget).trigger('change');

    // Preferred Locations (multiple select)
    if (client.preferred_location) {
        let locations = [];
        if (Array.isArray(client.preferred_location)) locations = client.preferred_location;
        else if (typeof client.preferred_location === 'string') {
            try {
                locations = JSON.parse(client.preferred_location);
                if (!Array.isArray(locations)) locations = [client.preferred_location];
            } catch {
                locations = client.preferred_location.includes(',')
                    ? client.preferred_location.split(',').map(loc => loc.trim())
                    : [client.preferred_location];
            }
        }
        $('#preferredLocation').val(locations).trigger('change');
    } else {
        $('#preferredLocation').val(null).trigger('change');
    }

    // Preferred Projects (multiple select)
    if (client.preferred_projects) {
        try {
            const projectIds = JSON.parse(client.preferred_projects);
            $('select[name="preferred_projects"]').val(projectIds).trigger('change');
        } catch {
            $('select[name="preferred_projects"]').val(null).trigger('change');
        }
    } else {
        $('select[name="preferred_projects"]').val(null).trigger('change');
    }
}

// Load locations dynamically (returns Promise)
function loadLocations() {
    return fetch('/api/locations')
        .then(response => response.json())
        .then(locations => {
            const preferredLocationSelect = document.getElementById('preferredLocation');
            const currentLocationSelect = document.getElementById('currentLocation');

            clearSelectOptions(preferredLocationSelect);
            clearSelectOptions(currentLocationSelect);

            locations.forEach(location => {
                preferredLocationSelect.add(new Option(location.name, location.name));
                if (currentLocationSelect) currentLocationSelect.add(new Option(location.name, location.name));
            });

            $('.select2-location').select2({
                placeholder: "Select location",
                allowClear: true,
                width: '100%'
            });
        })
        .catch(error => console.error('Error loading locations:', error));
}



function clearSelectOptions(selectElement) {
    // Keep only the first option (placeholder)
    while (selectElement.options.length > 1) {
        selectElement.remove(1);
    }
}

// Load locations when the page loads
document.addEventListener('DOMContentLoaded', function () {
    loadLocations();
});

// Also load locations when client data section is shown
document.getElementById('verifyMobile').addEventListener('click', function () {
    // This will run after the verification, so locations will be loaded when needed
    setTimeout(loadLocations, 100);
});
// Helper: Get query param from URL
function getQueryParam(param) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(param);
}

document.addEventListener('DOMContentLoaded', function () {
    const mobileFromQuery = getQueryParam('mobile');

    if (mobileFromQuery && /^\d{10}$/.test(mobileFromQuery)) {
        const mobileInput = document.getElementById('mobileNumber');
        mobileInput.value = mobileFromQuery;

        // Wait for locations to load before verifying
        // Use a small delay to ensure Select2 + options are ready
        setTimeout(() => {
            document.getElementById('verifyMobile').click();
        }, 1500);
    }
});
