// Form Submission Logic
document.getElementById('visitsForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    // Basic validation
    const mobile = document.querySelector('input[name="mobile"]').value;
    const name = document.querySelector('input[name="name"]').value;
    
    if (!name.trim()) {
        alert('Please enter client name');
        return;
    }
    
    if (!mobile.trim()) {
        alert('Please verify mobile number first');
        return;
    }
    
    const visitCards = document.querySelectorAll('.visit-card');
    if (visitCards.length === 0) {
        alert('Please add at least one site visit');
        return;
    }
    
    // Validate each visit
    let hasErrors = false;
    visitCards.forEach((card, index) => {
        const visitDate = card.querySelector('input[name*="visit_date"]').value;
        const projectId = card.querySelector('select[name*="project_id"]').value;
        
        if (!visitDate || !projectId) {
            alert(`Visit #${index + 1} is missing required fields (date or project)`);
            hasErrors = true;
        }
    });
    
    if (hasErrors) return;

    const submitBtn = this.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Saving...';

    // Collect form data
    const data = {
        mobile: mobile,
        name: name,
        email: document.querySelector('input[name="email"]').value,
        secondary_number: document.querySelector('input[name="secondary_number"]').value,
        lead_source: document.querySelector('select[name="lead_source"]').value,
        lead_source_project: document.querySelector('input[name="lead_source_project"]').value,
        bhk_requirement: document.querySelector('select[name="bhk_requirement"]').value,
        budget: document.querySelector('select[name="budget"]').value,
        preferred_location: document.querySelector('select[name="preferred_location"]').value,
        current_location: document.querySelector('select[name="current_location"]').value,
        building_name: document.querySelector('input[name="building_name"]').value,
        notes: document.querySelector('textarea[name="notes"]').value,
        visits: []
    };
    
    // Handle multiple select fields for client
    const preferredProjectsSelect = document.querySelector('select[name="preferred_projects"]');
    data.preferred_projects = $(preferredProjectsSelect).val() || [];

    // Collect visits data - FIXED: using the same visitCards variable
    visitCards.forEach((card, index) => {
        const visitData = {
            visit_date: card.querySelector(`input[name="visits[${index}][visit_date]"]`).value,
            project_id: card.querySelector(`select[name="visits[${index}][project_id]"]`).value,
            telecallers_involved: card.querySelector(`input[name="visits[${index}][telecallers_involved]"]`).value,
            visit_notes: card.querySelector(`textarea[name="visits[${index}][visit_notes]"]`).value
        };
        
        // Handle agents involved (multiple select)
        const agentsSelect = card.querySelector(`select[name="visits[${index}][agents_involved]"]`);
        visitData.agents_involved = $(agentsSelect).val() || [];
        
        data.visits.push(visitData);
    });

    console.log("Sending data to save:", data);

    fetch('/save-visits', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(result => {
        console.log("Save result:", result);
        if (result.success) {
            // alert(`Successfully logged ${data.visits.length} site visit(s)!`);
            // window.location.href = '/';
        } else {
            alert('Error: ' + result.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error saving site visits. Please try again.');
    })
    .finally(() => {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-save me-1"></i>Save All Visits';
    });
});