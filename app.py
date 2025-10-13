from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from models import db, User, Project, Client, SiteVisit,Location
from datetime import datetime
import json
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'mysql+pymysql://mysql:0YFsky4InHVxVnMRXJvYNEnBu5cPGUTtaZmefXbtVfcFOnIEBWKNbM0fUPml90b0'
    '@147.93.110.147:5665/default'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,       # Recycle connections every 5 minutes
    'pool_pre_ping': True,     # Test the connection before using it
}

db.init_app(app)  # <- Important!
# from sqlalchemy import text

# with app.app_context():
#     try:
#         wait_timeout = db.session.execute(text("SHOW VARIABLES LIKE 'wait_timeout'")).fetchone()
#         interactive_timeout = db.session.execute(text("SHOW VARIABLES LIKE 'interactive_timeout'")).fetchone()
#         connect_timeout = db.session.execute(text("SHOW VARIABLES LIKE 'connect_timeout'")).fetchone()

#         print(f"wait_timeout: {wait_timeout[1]}")
#         print(f"interactive_timeout: {interactive_timeout[1]}")
#         print(f"connect_timeout: {connect_timeout[1]}")

#     except Exception as e:
#         print("Error fetching timeout variables:", e)

# Option 1: Run inside a script



login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_data():
    projects = Project.query.all()
    agents = User.query.filter_by(role='agent').all()
    return dict(projects=projects, agents=agents)

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Main routes
@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/visit-logs')
@login_required
def get_visit_logs():
    search = request.args.get('search', '').strip()
    agent_filter = request.args.get('agent')
    project_filter = request.args.get('project')
    status_filter = request.args.get('status')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Base query
    query = SiteVisit.query.join(Client).join(Project)

    # Search: by name or mobile
    if search:
        query = query.filter(
            db.or_(
                Client.name.ilike(f"%{search}%"),
                Client.mobile.ilike(f"%{search}%")
            )
        )

    # Role-based restriction (agents only see their visits)
    if current_user.role == 'agent':
        query = query.filter(
            db.or_(
                SiteVisit.agents_involved.contains(str(current_user.id)),
                SiteVisit.created_by == current_user.id
            )
        )

    # Filters
    if agent_filter:
        query = query.filter(SiteVisit.agents_involved.contains(agent_filter))

    if project_filter:
        query = query.filter(SiteVisit.project_id == project_filter)

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(SiteVisit.visit_date >= start_dt)
        except ValueError:
            pass  # optional: log bad date input

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(SiteVisit.visit_date <= end_dt)
        except ValueError:
            pass

    # Fetch and order
    visits = query.order_by(SiteVisit.visit_date.desc()).all()

    # Build response
    result = []
    for visit in visits:
        agent_names = []
        try:
            agents = json.loads(visit.agents_involved or '[]')
            agent_objs = User.query.filter(User.id.in_(agents)).all()
            agent_names = [agent.name for agent in agent_objs]
        except Exception as e:
            print("Error parsing agents:", e)

        result.append({
            'id': visit.id,
            'agent': ', '.join(agent_names),
            'client_name': visit.client.name,
            'client_mobile': visit.client.mobile,
            'project_name': visit.project.name,
            'visit_date': visit.visit_date.strftime('%b %d, %Y'),
            'status': visit.status or 'Upcoming', 
            'bhk_requirement': visit.client.bhk_requirement or '',
            'can_delete': current_user.role == 'admin' or current_user.id == visit.created_by
        })

    return jsonify(result)

@app.route('/visit/<int:visit_id>')
@login_required
def visit_details(visit_id):
    visit = SiteVisit.query.get_or_404(visit_id)
    print(visit.agents_involved)
    
    if current_user.role == 'agent':
        agents_involved = json.loads(visit.agents_involved) if visit.agents_involved else []
        if current_user.id not in [int(x) for x in agents_involved] and visit.created_by != current_user.id:
            flash('Access denied', 'danger')
            return redirect(url_for('dashboard'))
    
    # Get previous visits for this client (excluding current visit)
    previous_visits = SiteVisit.query.filter(
        SiteVisit.client_id == visit.client_id,
        SiteVisit.id != visit.id
    ).order_by(SiteVisit.visit_date.desc()).all()
    
    return render_template('visit_details.html', visit=visit, previous_visits=previous_visits)
@app.route('/visit/<int:visit_id>/update_details', methods=['POST'])
@login_required
def update_visit_details(visit_id):
    visit = SiteVisit.query.get_or_404(visit_id)

    # Permission check
    if current_user.role == 'admin':
        pass
    elif current_user.role == 'agent':
        agents_involved = json.loads(visit.agents_involved) if visit.agents_involved else []
        if current_user.id not in [int(x) for x in agents_involved] and visit.created_by != current_user.id:
            flash('Access denied.', 'danger')
            return redirect(url_for('visit_details', visit_id=visit_id))
    else:
        flash('Access denied.', 'danger')
        return redirect(url_for('visit_details', visit_id=visit_id))

    # Update visit_date
    visit_date_str = request.form.get('visit_date')
    if not visit_date_str:
        flash('No visit date provided.', 'danger')
        return redirect(url_for('visit_details', visit_id=visit_id))

    try:
        visit.visit_date = datetime.strptime(visit_date_str, '%Y-%m-%d')
        db.session.commit()
        flash('Visit date updated successfully.', 'success')
    except ValueError:
        flash('Invalid date format.', 'danger')

    return redirect(url_for('visit_details', visit_id=visit_id))


@app.route('/api/visit/<int:visit_id>/delete', methods=['DELETE'])
@login_required
def api_delete_visit(visit_id):
    visit = SiteVisit.query.get_or_404(visit_id)

    if current_user.role != 'admin' and current_user.id != visit.created_by:
        return jsonify({'message': 'Access denied'}), 403

    db.session.delete(visit)
    db.session.commit()

    return jsonify({'message': 'Visit deleted successfully'})


@app.route('/visit/<int:visit_id>/update_status', methods=['POST'])
@login_required
def update_visit_status(visit_id):
    visit = SiteVisit.query.get_or_404(visit_id)

    # Admin can update any visit
    if current_user.role == 'admin':
        pass
    # Agents can only update if involved or creator
    elif current_user.role == 'agent':
        agents_involved = json.loads(visit.agents_involved) if visit.agents_involved else []
        if current_user.id not in [int(x) for x in agents_involved] and visit.created_by != current_user.id:
            flash('Access denied: You are not authorized to update this visit.', 'danger')
            return redirect(url_for('visit_details', visit_id=visit_id))
    else:
        # Other roles are denied
        flash('Access denied: You are not authorized to update this visit.', 'danger')
        return redirect(url_for('visit_details', visit_id=visit_id))

    # Validate new status
    new_status = request.form.get('status')
    if new_status not in ['Scheduled', 'Completed', 'Cancelled']:
        flash('Invalid status.', 'danger')
        return redirect(url_for('visit_details', visit_id=visit_id))

    visit.status = new_status
    db.session.commit()

    flash('Visit status updated successfully.', 'success')
    return redirect(url_for('visit_details', visit_id=visit_id))

@app.route('/log-visit', methods=['GET', 'POST'])
@login_required
def log_visit():
    if request.method == 'POST':
        mobile = request.form.get('mobile')
        print(f"Verifying mobile: {mobile}")  # Debug print
        
        if not mobile:
            return jsonify({'error': 'Mobile number is required'}), 400
        
        client = Client.query.filter_by(mobile=mobile).first()
        
        if client:
            # Get previous visits - FIXED: Query SiteVisit directly instead of using relationship
            previous_visits_query = SiteVisit.query.filter_by(client_id=client.id).order_by(SiteVisit.visit_date.desc()).all()
            previous_visits = []
            
            for visit in previous_visits_query:
                agents_list = []
                if visit.agents_involved:
                    try:
                        agent_ids = json.loads(visit.agents_involved)
                        for agent_id in agent_ids:
                            agent = User.query.get(agent_id)
                            if agent:
                                agents_list.append(agent.name)
                    except:
                        pass
                
                previous_visits.append({
                    'date': visit.visit_date.strftime('%b %d, %Y'),
                    'project': visit.project.name,
                    'status': visit.status,
                    'agents': ', '.join(agents_list)
                })
            
            return jsonify({
                'exists': True,
                'client': {
                    'name': client.name or '',
                    'email': client.email or '',
                    'secondary_number': client.secondary_number or '',
                    'lead_source': client.lead_source or '',
                    'lead_source_project': client.lead_source_project or '',
                    'bhk_requirement': client.bhk_requirement or '',
                    'budget': client.budget or '',
                    'preferred_location': client.preferred_location or '',
                    'current_location': client.current_location or '',
                    'building_name': client.building_name or '',
                    'preferred_projects': client.preferred_projects or '[]',
                    'notes': client.notes or ''
                },
                'previous_visits': previous_visits
            })
        else:
            return jsonify({'exists': False})
    
    projects = Project.query.all()
    users = User.query.filter_by(role='agent').all()
    return render_template('log_visit.html', projects=projects, users=users)
# @app.route('/save-visit', methods=['POST'])
# @login_required
# def save_visit():
#     try:
#         data = request.get_json()
#         print("Received data:", data)  # Debug print
        
#         # Validate required fields
#         if not data.get('name') or not data.get('mobile') or not data.get('visit_date') or not data.get('project_id'):
#             return jsonify({'success': False, 'message': 'Missing required fields'})
        
#         # Check if client exists
#         client = Client.query.filter_by(mobile=data['mobile']).first()
        
#         if not client:
#             # Create new client
#             client = Client(
#                 name=data['name'],
#                 mobile=data['mobile'],
#                 email=data.get('email', ''),
#                 secondary_number=data.get('secondary_number', ''),
#                 lead_source=data.get('lead_source', ''),
#                 lead_source_project=data.get('lead_source_project', ''),
#                 bhk_requirement=data.get('bhk_requirement', ''),
#                 budget=data.get('budget', ''),
#                 preferred_location=data.get('preferred_location', ''),
#                 current_location=data.get('current_location', ''),
#                 building_name=data.get('building_name', ''),
#                 preferred_projects=json.dumps(data.get('preferred_projects', [])),
#                 notes=data.get('notes', ''),
#                 created_by=current_user.id
#             )
#             db.session.add(client)
#             db.session.flush()  # Get the client ID without committing
#         else:
#             # Update existing client
#             client.name = data['name']
#             client.email = data.get('email', '')
#             client.secondary_number = data.get('secondary_number', '')
#             client.lead_source = data.get('lead_source', '')
#             client.lead_source_project = data.get('lead_source_project', '')
#             client.bhk_requirement = data.get('bhk_requirement', '')
#             client.budget = data.get('budget', '')
#             client.preferred_location = data.get('preferred_location', '')
#             client.current_location = data.get('current_location', '')
#             client.building_name = data.get('building_name', '')
#             client.preferred_projects = json.dumps(data.get('preferred_projects', []))
#             client.notes = data.get('notes', '')
        
#         # Process agents involved
#         agents_involved = data.get('agents_involved', [])
#         if isinstance(agents_involved, str):
#             agents_involved = [agents_involved] if agents_involved else []
        
#         # Ensure current user is included
#         if str(current_user.id) not in agents_involved:
#             agents_involved.append(str(current_user.id))
        
#         # Process telecallers
#         telecallers = data.get('telecallers_involved', '')
#         if telecallers:
#             telecallers_list = [t.strip() for t in telecallers.split(',') if t.strip()]
#         else:
#             telecallers_list = []
        
#         # Create site visit
#         visit = SiteVisit(
#             client_id=client.id,
#             visit_date=datetime.strptime(data['visit_date'], '%Y-%m-%d'),
#             project_id=int(data['project_id']),
#             agents_involved=json.dumps(agents_involved),
#             telecallers_involved=json.dumps(telecallers_list),
#             notes=data.get('visit_notes', ''),
#             created_by=current_user.id
#         )
        
#         db.session.add(visit)
#         db.session.commit()
        
#         return jsonify({'success': True, 'message': 'Site visit logged successfully'})
    
#     except Exception as e:
#         db.session.rollback()
#         print("Error saving visit:", str(e))  # Debug print
#         return jsonify({'success': False, 'message': f'Error: {str(e)}'})
@app.route('/save-visits', methods=['POST'])
@login_required
def save_visits():
    try:
        data = request.get_json()
        print("Received data for multiple visits:", data)  # Debug print
        
        # Validate required fields
        if not data.get('name') or not data.get('mobile'):
            return jsonify({'success': False, 'message': 'Missing client name or mobile'})
        
        if not data.get('visits') or len(data.get('visits', [])) == 0:
            return jsonify({'success': False, 'message': 'No site visits provided'})
        
        # Validate each visit
        for i, visit_data in enumerate(data['visits']):
            if not visit_data.get('visit_date') or not visit_data.get('project_id'):
                return jsonify({'success': False, 'message': f'Visit #{i+1} missing required fields (date or project)'})
        
        # Check if client exists
        client = Client.query.filter_by(mobile=data['mobile']).first()
        
        if not client:
            # Create new client
            client = Client(
                name=data['name'],
                mobile=data['mobile'],
                email=data.get('email', ''),
                secondary_number=data.get('secondary_number', ''),
                lead_source=data.get('lead_source', ''),
                lead_source_project=data.get('lead_source_project', ''),
                bhk_requirement=data.get('bhk_requirement', ''),
                budget=data.get('budget', ''),
                preferred_location=data.get('preferred_location', ''),
                current_location=data.get('current_location', ''),
                building_name=data.get('building_name', ''),
                preferred_projects=json.dumps(data.get('preferred_projects', [])),
                notes=data.get('notes', ''),
                ethnicity=data.get('ethnicity', ''),
                created_by=current_user.id
            )
            db.session.add(client)
            db.session.flush()  # Get the client ID without committing
            print(f"Created new client with ID: {client.id}")
        else:
            # Update existing client
            client.name = data['name']
            client.email = data.get('email', '')
            client.secondary_number = data.get('secondary_number', '')
            client.lead_source = data.get('lead_source', '')
            client.lead_source_project = data.get('lead_source_project', '')
            client.bhk_requirement = data.get('bhk_requirement', '')
            client.budget = data.get('budget', '')
            client.preferred_location = data.get('preferred_location', '')
            client.current_location = data.get('current_location', '')
            client.building_name = data.get('building_name', '')
            client.preferred_projects = json.dumps(data.get('preferred_projects', []))
            client.notes = data.get('notes', '')
            client.ethnicity = data.get('ethnicity', '')
            print(f"Updated existing client with ID: {client.id}")
        
        # Process and save all visits
        saved_visits = []
        for i, visit_data in enumerate(data['visits']):
            # Process agents involved for this visit
            agents_involved = visit_data.get('agents_involved', [])
            if isinstance(agents_involved, str):
                agents_involved = [agents_involved] if agents_involved else []
            
            # Ensure current user is included in agents
            if str(current_user.id) not in agents_involved:
                agents_involved.append(str(current_user.id))
            
            # Process telecallers for this visit
            telecallers = visit_data.get('telecallers_involved', '')
            if telecallers:
                telecallers_list = [t.strip() for t in telecallers.split(',') if t.strip()]
            else:
                telecallers_list = []
            
            # Create site visit
            visit = SiteVisit(
                client_id=client.id,
                visit_date=datetime.strptime(visit_data['visit_date'], '%Y-%m-%d'),
                project_id=int(visit_data['project_id']),
                status=visit_data['status'],
                agents_involved=json.dumps(agents_involved),
                telecallers_involved=json.dumps(telecallers_list),
                notes=visit_data.get('visit_notes', ''),
                created_by=current_user.id
            )
            
            db.session.add(visit)
            saved_visits.append(visit)
            print(f"Created visit #{i+1} for project ID: {visit_data['project_id']}")
        
        # Commit all changes
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Successfully logged {len(saved_visits)} site visit(s) for client {client.name}',
            'client_id': client.id,
            'visits_count': len(saved_visits)
        })
    
    except Exception as e:
        db.session.rollback()
        print("Error saving visits:", str(e))
        import traceback
        traceback.print_exc()  # Print full traceback for debugging
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})
@app.route('/user-management')
@login_required
def user_management():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    users = User.query.all()
    return render_template('user_management.html', users=users)

@app.route('/add-user', methods=['POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'})
    
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        role = request.form.get('role')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'message': 'User with this email already exists'})
        
        user = User(
            name=name,
            email=email,
            role=role,
            password=generate_password_hash(password)
        )
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'User added successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/project-management')
@login_required
def project_management():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    projects = Project.query.all()
    return render_template('project_management.html', projects=projects)

@app.route('/add-project', methods=['POST'])
@login_required
def add_project():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'})
    
    try:
        name = request.form.get('name')
        
        if Project.query.filter_by(name=name).first():
            return jsonify({'success': False, 'message': 'Project with this name already exists'})
        
        project = Project(name=name)
        db.session.add(project)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Project added successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})
# routes/locations.py or add to your main routes file
@app.route('/locations')
@login_required
def locations_management():
    locations = Location.query.filter_by(is_active=True).order_by(Location.name).all()
    return render_template('locations.html', locations=locations)

@app.route('/locations/create', methods=['POST'])
@login_required
def create_location():
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        
        if not name:
            return jsonify({'success': False, 'message': 'Location name is required'})
        
        # Check if location already exists
        existing_location = Location.query.filter(
            db.func.lower(Location.name) == db.func.lower(name),
            Location.is_active == True
        ).first()
        
        if existing_location:
            return jsonify({'success': False, 'message': 'Location already exists'})
        
        # Create new location
        location = Location(
            name=name,
            description=description,
            created_by=current_user.id
        )
        
        db.session.add(location)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Location created successfully',
            'location': {
                'id': location.id,
                'name': location.name,
                'description': location.description
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/locations/<int:location_id>/delete', methods=['POST'])
@login_required
def delete_location(location_id):
    try:
        location = Location.query.get_or_404(location_id)
        
        # Check if location is being used in any client records
        preferred_location_clients = Client.query.filter(
            Client.preferred_location == location.name
        ).count()
        
        current_location_clients = Client.query.filter(
            Client.current_location == location.name
        ).count()
        
        if preferred_location_clients > 0 or current_location_clients > 0:
            return jsonify({
                'success': False, 
                'message': f'Cannot delete location. It is being used by {preferred_location_clients + current_location_clients} client(s).'
            })
        
        # Soft delete by setting is_active to False
        location.is_active = False
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Location deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/locations')
@login_required
def get_locations_api():
    locations = Location.query.filter_by(is_active=True).order_by(Location.name).all()
    locations_list = [{'id': loc.id, 'name': loc.name} for loc in locations]
    return jsonify(locations_list)
# Custom filter for templates
@app.template_filter('from_json')
def from_json_filter(value):
    try:
        return json.loads(value) if value else []
    except:
        return []

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Create default users if they don't exist
        if not User.query.filter_by(email='admin@realestate.com').first():
            admin = User(
                name='Admin User',
                email='admin@realestate.com',
                password=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
            
        if not User.query.filter_by(email='jane@realestate.com').first():
            agent1 = User(
                name='Jane Smith',
                email='jane@realestate.com',
                password=generate_password_hash('agent123'),
                role='agent'
            )
            db.session.add(agent1)
            
        if not User.query.filter_by(email='mike@realestate.com').first():
            agent2 = User(
                name='Mike Johnson',
                email='mike@realestate.com',
                password=generate_password_hash('agent123'),
                role='agent'
            )
            db.session.add(agent2)
        
        if Project.query.count() == 0:
            projects = [
                'Sunset Meadows', 'Urban Heights', 'Green Valley', 
                'City Center Lofts', 'Riverside Residences', 
                'Mountain View Estates', 'Harbor Point Towers'
            ]
            for project_name in projects:
                project = Project(name=project_name)
                db.session.add(project)
        
        db.session.commit()
        print("Database initialized successfully!")
        print("Default users created:")
        print("Admin: admin@realestate.com / admin123")
        print("Agent: jane@realestate.com / agent123")
        print("Agent: mike@realestate.com / agent123")
    
    app.run(debug=True,port=4554)