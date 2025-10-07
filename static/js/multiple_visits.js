// Multiple Visits Management
let visitCounter = 1;

document.getElementById('addVisitBtn').addEventListener('click', function() {
    addNewVisitCard();
});

function addNewVisitCard() {
    visitCounter++;
    const today = new Date().toISOString().split('T')[0];
    
    const newVisitCard = document.createElement('div');
    newVisitCard.className = 'visit-card card border-primary mb-3';
    newVisitCard.innerHTML = `
        <div class="card-header bg-light d-flex justify-content-between align-items-center">
            <h6 class="mb-0">Visit #${visitCounter}</h6>
            <button type="button" class="btn btn-outline-danger btn-sm remove-visit">
                <i class="fas fa-times"></i>
            </button>
        </div>
        <div class="card-body">
            <div class="row g-3">
                <div class="col-md-6">
                    <label class="form-label">Visit Date *</label>
                    <input type="date" class="form-control visit-date" name="visits[${visitCounter-1}][visit_date]" value="${today}" required>
                </div>
                <div class="col-md-6">
                    <label class="form-label">Project *</label>
                    <select class="form-select" name="visits[${visitCounter-1}][project_id]" required>
                        <option value="">Select a project</option>
                        ${getProjectsOptions()}
                    </select>
                </div>
                <div class="col-md-6">
                    <label class="form-label">Agents Involved</label>
                    <select class="form-select select2-visit" name="visits[${visitCounter-1}][agents_involved]" multiple>
                        ${getUsersOptions()}
                    </select>
                    <div class="form-text">Select agents involved in this visit</div>
                </div>
                <div class="col-md-6 d-none">
                    <label class="form-label">Telecallers Involved</label>
                    <input type="text" class="form-control" value="None" name="visits[${visitCounter-1}][telecallers_involved]" 
                           placeholder="Enter telecaller names separated by commas">
                </div>
                <div class="col-12">
                    <label class="form-label">Visit Notes</label>
                    <textarea class="form-control" name="visits[${visitCounter-1}][visit_notes]" rows="3" 
                              placeholder="Enter notes about this specific site visit"></textarea>
                </div>
            </div>
        </div>
    `;
    
    document.getElementById('visitsContainer').appendChild(newVisitCard);
    
    // Initialize Select2 for the new select elements
    $(newVisitCard).find('.select2-visit').select2({
        placeholder: "Select agents",
        allowClear: true,
        width: '100%'
    });
    
    // Add remove functionality
    newVisitCard.querySelector('.remove-visit').addEventListener('click', function() {
        if (visitCounter > 1) {
            newVisitCard.remove();
            visitCounter--;
            renumberVisitCards();
            updateRemoveButtons();
        }
    });
    
    // Show remove buttons on all cards if there's more than one visit
    updateRemoveButtons();
}

function getProjectsOptions() {
    // Extract projects from the existing select in the first visit card
    const firstProjectSelect = document.querySelector('select[name="visits[0][project_id]"]');
    if (firstProjectSelect) {
        return firstProjectSelect.innerHTML;
    }
    return '';
}

function getUsersOptions() {
    // Extract users from the existing select in the first visit card
    const firstAgentsSelect = document.querySelector('select[name="visits[0][agents_involved]"]');
    if (firstAgentsSelect) {
        // Clone the options to avoid reference issues
        return firstAgentsSelect.innerHTML;
    }
    return '';
}

function renumberVisitCards() {
    const visitCards = document.querySelectorAll('.visit-card');
    visitCards.forEach((card, index) => {
        const header = card.querySelector('.card-header h6');
        header.textContent = `Visit #${index + 1}`;
        
        // Update all input names with new index
        const inputs = card.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            const oldName = input.name;
            // Use regex to replace the index in the name
            const newName = oldName.replace(/visits\[\d+\]/g, `visits[${index}]`);
            input.name = newName;
        });
    });
}

function updateRemoveButtons() {
    const removeButtons = document.querySelectorAll('.remove-visit');
    const shouldShow = visitCounter > 1;
    removeButtons.forEach(button => {
        button.style.display = shouldShow ? 'block' : 'none';
    });
}

// Initialize remove button visibility
document.addEventListener('DOMContentLoaded', function() {
    updateRemoveButtons();
});