// Mobile Verification Logic
document.addEventListener('DOMContentLoaded', function() {
    // Set default visit date to today for first visit
    const today = new Date().toISOString().split('T')[0];
    document.querySelector('.visit-date').value = today;
});

document.getElementById('verifyMobile').addEventListener('click', function() {
    const mobile = document.getElementById('mobileNumber').value.trim();
    
    if (!mobile || mobile.length !== 10 || !/^\d+$/.test(mobile)) {
        alert('Please enter a valid 10-digit mobile number');
        return;
    }

    const verifyBtn = this;
    verifyBtn.disabled = true;
    verifyBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Verifying...';

    // Create form data for POST request
    const formData = new URLSearchParams();
    formData.append('mobile', mobile);

    fetch('/log-visit', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData
    })
    .then(response => {
        console.log('Response status:', response.status);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Verification response:', data);
        
        const clientSection = document.getElementById('clientDataSection');
        const previousVisitsCard = document.getElementById('previousVisitsCard');
        const previousVisitsList = document.getElementById('previousVisitsList');
        
        clientSection.style.display = 'block';
        document.querySelector('input[name="mobile"]').value = mobile;

        if (data.exists) {
            console.log('Client exists, filling form...');
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
            console.log('New client, clearing form...');
            previousVisitsCard.style.display = 'none';
            previousVisitsList.innerHTML = '';
            // Clear form for new client (except mobile)
            document.getElementById('visitsForm').reset();
            document.querySelector('input[name="mobile"]').value = mobile;
            // Reset Select2 fields
            $('.select2').val(null).trigger('change');
        }
        
        // Scroll to client section
        clientSection.scrollIntoView({ behavior: 'smooth' });
    })
    .catch(error => {
        console.error('Verification error:', error);
        // alert('Error verifying mobile number. Please try again.');
    })
    .finally(() => {
        verifyBtn.disabled = false;
        verifyBtn.innerHTML = '<i class="fas fa-check me-1"></i>Verify';
    });
});

function fillClientForm(client) {
    // Fill basic fields
    document.querySelector('input[name="name"]').value = client.name || '';
    document.querySelector('input[name="email"]').value = client.email || '';
    document.querySelector('input[name="secondary_number"]').value = client.secondary_number || '';
    document.querySelector('input[name="lead_source_project"]').value = client.lead_source_project || '';
    document.querySelector('select[name="current_location"]').value = client.current_location || '';

    document.querySelector('select[name="preferred_location"]').value = client.preferred_location || '';

    document.querySelector('input[name="building_name"]').value = client.building_name || '';
    document.querySelector('textarea[name="notes"]').value = client.notes || '';
    
    // Fill select fields
    if (client.lead_source) {
        document.querySelector('select[name="lead_source"]').value = client.lead_source;
    }
    if (client.bhk_requirement) {
        document.querySelector('select[name="bhk_requirement"]').value = client.bhk_requirement;
    }
    if (client.budget) {
        document.querySelector('select[name="budget"]').value = client.budget;
    }
    $('select[name="preferred_location"]').val(client.preferred_location).trigger('change');
    $('select[name="current_location"]').val(client.current_location).trigger('change');
    // Fill preferred projects (multiple select)
    if (client.preferred_projects) {
        try {
            const projectIds = JSON.parse(client.preferred_projects);
            const projectsSelect = document.querySelector('select[name="preferred_projects"]');
            // Clear previous selections
            $(projectsSelect).val(null).trigger('change');
            // Select the projects
            if (projectIds.length > 0) {
                $(projectsSelect).val(projectIds).trigger('change');
            }
        } catch (e) {
            console.error('Error parsing preferred projects:', e);
        }
    }
}
// Location Management for Site Visit Form
function loadLocations() {
    fetch('/api/locations')
        .then(response => response.json())
        .then(locations => {
            const preferredLocationSelect = document.getElementById('preferredLocation');
            const currentLocationSelect = document.getElementById('currentLocation');
            
            // Clear existing options except the first one
            clearSelectOptions(preferredLocationSelect);
            clearSelectOptions(currentLocationSelect);
            
            // Add location options
            locations.forEach(location => {
                const option1 = new Option(location.name, location.name);
                const option2 = new Option(location.name, location.name);
                preferredLocationSelect.add(option1);
                currentLocationSelect.add(option2);
            });
            
            // Initialize Select2 for location dropdowns
            $('.select2-location').select2({
                placeholder: "Select location",
                allowClear: true,
                width: '100%'
            });
        })
        .catch(error => {
            console.error('Error loading locations:', error);
        });
}

function clearSelectOptions(selectElement) {
    // Keep only the first option (placeholder)
    while (selectElement.options.length > 1) {
        selectElement.remove(1);
    }
}

// Load locations when the page loads
document.addEventListener('DOMContentLoaded', function() {
    loadLocations();
});

// Also load locations when client data section is shown
document.getElementById('verifyMobile').addEventListener('click', function() {
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
