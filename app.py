from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import json
import pandas as pd
# Import your database models
from models import db, User, Project, Client, SiteVisit, Location
# Optional: Blueprint setup if needed
from flask import Blueprint
import re
from flask_mail import Mail, Message
from flask import request
import requests
from user_agents import parse
def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        # Sometimes multiple IPs are comma-separated; take the first one
        ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    else:
        ip = request.remote_addr
    return ip

def get_client_info():
    # Get IP
    ip_address = get_client_ip()

    # Get location from IP
    try:
        response = requests.get(f"https://ipapi.co/{ip_address}/json/").json()
        city = response.get("city")
        region = response.get("region")
        country = response.get("country_name")
    except:
        city = region = country = "Unknown"

    # Get browser and device
    user_agent = parse(request.headers.get('User-Agent'))
    browser = f"{user_agent.browser.family} {user_agent.browser.version_string}"
    os = f"{user_agent.os.family} {user_agent.os.version_string}"
    device = user_agent.device.family

    return {
        "ip": ip_address,
        "city": city,
        "region": region,
        "country": country,
        "browser": browser,
        "os": os,
        "device": device
    }


UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'xls', 'xlsx'}

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
app.config['MAIL_SERVER'] = 'smtp.elasticemail.com'  # or your mail server
app.config['MAIL_PORT'] = 2525
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'leads@valuepropertiesleads.in'
app.config['MAIL_PASSWORD'] = '63677F38ADD93ECB4ECDE395430EC87DC6C3'
app.config['MAIL_DEFAULT_SENDER'] = ('SVM Login Alerts', 'leads@valuepropertiesleads.in')


mail = Mail(app)

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

            # Capture client info
            info = get_client_info()

            # List of recipients: user + optional admin
            recipients = [email, 'krkl9v3@gmail.com']  # user + admin

            # Send email
            msg = Message(
                subject="New Login Notification",
                recipients=recipients,
                html=f"""
                <h3>New login detected</h3>
                <ul>
                    <li>User Name: {user.name}</li>
                    <li>User Email: {email}</li>
                    <li>IP Address: {info['ip']}</li>
                    <li>Location: {info['city']}, {info['region']}, {info['country']}</li>
                    <li>Browser: {info['browser']}</li>
                    <li>OS: {info['os']}</li>
                    <li>Device: {info['device']}</li>
                </ul>
                """
            )
            mail.send(msg)
            
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
# Simple email validation
def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

@app.route('/upload-sales-team', methods=['POST'])
@login_required
def upload_sales_team():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'})

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'})

    file = request.files['file']

    try:
        # Read Excel file
        df = pd.read_excel(file)

        # Check required columns
        if 'name' not in df.columns or 'email' not in df.columns:
            return jsonify({'success': False, 'message': 'Excel must contain "name" and "email" columns'})

        added_users = []
        skipped_rows = []

        for index, row in df.iterrows():
            # Convert NaN to None and strip strings
            name = str(row['name']).strip() if pd.notna(row['name']) else None
            email = str(row['email']).strip() if pd.notna(row['email']) else None

            # Skip invalid or missing data
            if not name or not email or not is_valid_email(email):
                skipped_rows.append({
                    'row': index + 2,  # Excel row number
                    'name': name,
                    'email': email,
                    'reason': 'Missing or invalid'
                })
                continue

            # Skip duplicates
            if User.query.filter_by(email=email).first():
                skipped_rows.append({
                    'row': index + 2,
                    'name': name,
                    'email': email,
                    'reason': 'Already exists'
                })
                continue

            # Generate password: first 3 letters of name + @123
            password = f"{name[:3]}@123"

            user = User(
                name=name,
                email=email,
                role='agent',
                password=generate_password_hash(password)
            )

            db.session.add(user)
            added_users.append(email)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Users added successfully: {added_users}',
            'skipped_rows': skipped_rows
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/full-filter', methods=['GET', 'POST'])
@login_required
def full_filter_visit_logs():
    # Fetch dropdown options
    agents = User.query.all()
    projects = Project.query.all()
    statuses = ['Upcoming', 'Completed', 'Cancelled']
    lead_sources = db.session.query(Client.lead_source).distinct().all()
    bhk_options = db.session.query(Client.bhk_requirement).distinct().all()
    budgets = db.session.query(Client.budget).distinct().all()
    # Collect all preferred locations (JSON arrays like ["BKC","Worli"])
    raw_locations = db.session.query(Client.preferred_location).distinct().all()

    unique_locations = set()
    for loc_entry in raw_locations:
        if not loc_entry[0]:
            continue
        try:
            loc_list = json.loads(loc_entry[0])
            if isinstance(loc_list, list):
                unique_locations.update(loc_list)
            else:
                unique_locations.add(loc_entry[0])
        except Exception:
            unique_locations.add(loc_entry[0])

    locations = sorted(unique_locations)

    current_locations = db.session.query(Client.current_location).distinct().all()
    ethnicities = db.session.query(Client.ethnicity).distinct().all()
    professions = db.session.query(Client.profession).distinct().all()

    # Collect filters
    filters = {
        'agent': request.form.get('agent'),
        'project': request.form.get('project'),
        'status': request.form.get('status'),
        'client_name': request.form.get('client_name', '').strip(),
        'client_mobile': request.form.get('client_mobile', '').strip(),
        'client_email': request.form.get('client_email', '').strip(),
        'lead_source': request.form.get('lead_source'),
        'lead_source_project': request.form.get('lead_source_project', '').strip(),
        'bhk_requirement': request.form.get('bhk_requirement'),
        'budget': request.form.get('budget'),
        'preferred_location': request.form.get('preferred_location'),
        'current_location': request.form.get('current_location'),
        'building_name': request.form.get('building_name', '').strip(),
        'preferred_projects': request.form.get('preferred_projects', '').strip(),
        'ethnicity': request.form.get('ethnicity'),
        'profession': request.form.get('profession'),
        'client_notes': request.form.get('client_notes', '').strip(),
        'telecallers': request.form.get('telecallers', '').strip(),
        'visit_notes': request.form.get('visit_notes', '').strip(),
        'start_date': request.form.get('start_date'),
        'end_date': request.form.get('end_date'),
    }
    
    # Base query
    query = SiteVisit.query.join(Client).join(Project)

    # Role-based restriction
    if current_user.role == 'agent':
        query = query.filter(
            db.or_(
                SiteVisit.agents_involved.contains(str(current_user.id)),
                SiteVisit.created_by == current_user.id
            )
        )

    # Apply filters
    if filters['agent']:
        query = query.filter(SiteVisit.agents_involved.contains(filters['agent']))

    if filters['project']:
        query = query.filter(SiteVisit.project_id == filters['project'])

    if filters['status']:
        query = query.filter(SiteVisit.status == filters['status'])

    if filters['client_name']:
        query = query.filter(Client.name.ilike(f"%{filters['client_name']}%"))

    if filters['client_mobile']:
        query = query.filter(Client.mobile.ilike(f"%{filters['client_mobile']}%"))

    if filters['client_email']:
        query = query.filter(Client.email.ilike(f"%{filters['client_email']}%"))

    if filters['lead_source']:
        query = query.filter(Client.lead_source == filters['lead_source'])

    if filters['lead_source_project']:
        query = query.filter(Client.lead_source_project.ilike(f"%{filters['lead_source_project']}%"))

    if filters['bhk_requirement']:
        query = query.filter(Client.bhk_requirement == filters['bhk_requirement'])

    if filters['budget']:
        query = query.filter(Client.budget == filters['budget'])

    if filters['preferred_location']:
        query = query.filter(Client.preferred_location.contains(filters['preferred_location']))


    if filters['current_location']:
        query = query.filter(Client.current_location == filters['current_location'])

    if filters['building_name']:
        query = query.filter(Client.building_name.ilike(f"%{filters['building_name']}%"))

    if filters['preferred_projects']:
        query = query.filter(Client.preferred_projects.contains(filters['preferred_projects']))

    if filters['ethnicity']:
        query = query.filter(Client.ethnicity == filters['ethnicity'])

    if filters['profession']:
        query = query.filter(Client.profession == filters['profession'])

    if filters['client_notes']:
        query = query.filter(Client.notes.ilike(f"%{filters['client_notes']}%"))

    if filters['telecallers']:
        query = query.filter(SiteVisit.telecallers_involved.contains(filters['telecallers']))

    if filters['visit_notes']:
        query = query.filter(SiteVisit.notes.ilike(f"%{filters['visit_notes']}%"))

    if filters['start_date']:
        try:
            start_dt = datetime.strptime(filters['start_date'], '%Y-%m-%d')
            query = query.filter(SiteVisit.visit_date >= start_dt)
        except ValueError:
            pass

    if filters['end_date']:
        try:
            end_dt = datetime.strptime(filters['end_date'], '%Y-%m-%d')
            query = query.filter(SiteVisit.visit_date <= end_dt)
        except ValueError:
            pass

    visits = query.order_by(SiteVisit.visit_date.desc()).all()

    # Build results
    result = []
    for visit in visits:
        agent_names = []
        try:
            agents_list = json.loads(visit.agents_involved or '[]')
            agent_objs = User.query.filter(User.id.in_(agents_list)).all()
            agent_names = [agent.name for agent in agent_objs]
        except Exception as e:
            print("Error parsing agents:", e)
        preferred_projects = []
        try:
            if visit.client.preferred_projects:
                project_ids = json.loads(visit.client.preferred_projects)
                project_objs = Project.query.filter(Project.id.in_(project_ids)).all()
                preferred_projects = [p.name for p in project_objs]
        except Exception as e:
            print("Error parsing preferred projects:", e)

        # Decode preferred locations
        preferred_locations_display = ""
        try:
            if visit.client.preferred_location:
                loc_list = json.loads(visit.client.preferred_location)
                if isinstance(loc_list, list):
                    preferred_locations_display = ", ".join(loc_list)
                else:
                    preferred_locations_display = visit.client.preferred_location
        except Exception as e:
            preferred_locations_display = visit.client.preferred_location or ''
        result.append({
            'id': visit.id,
            'agent': ', '.join(agent_names),
            'client_name': visit.client.name,
            'client_mobile': visit.client.mobile,
            'client_email': visit.client.email,
            'lead_source': visit.client.lead_source,
            'lead_source_project': visit.client.lead_source_project,
            'bhk_requirement': visit.client.bhk_requirement,
            'budget': visit.client.budget,
            'preferred_location': preferred_locations_display,
            'current_location': visit.client.current_location,
            'building_name': visit.client.building_name,
            'preferred_projects': ', '.join(preferred_projects),
            'ethnicity': visit.client.ethnicity,
            'profession': visit.client.profession,
            'client_notes': visit.client.notes,
            'project_name': visit.project.name,
            'visit_date': visit.visit_date.strftime('%b %d, %Y'),
            'status': visit.status or 'Upcoming',
            'telecallers': visit.telecallers_involved,
            'visit_notes': visit.notes,
            'can_delete': current_user.role == 'admin' or current_user.id == visit.created_by
        })

    return render_template(
        'full_advanced_visit_logs.html',
        visits=result,
        agents=agents,
        projects=projects,
        statuses=statuses,
        lead_sources=[l[0] for l in lead_sources],
        bhk_options=[b[0] for b in bhk_options],
        budgets=[b[0] for b in budgets],
        locations=locations,
        current_locations=[l[0] for l in current_locations],
        ethnicities=[e[0] for e in ethnicities],
        professions=[p[0] for p in professions],
        filters=filters
    )

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

    # Access control: only agents involved or creator can view
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

    # ✅ Convert preferred_location JSON -> location names
    preferred_location_names = []
    if visit.client.preferred_location:
        try:
            loc_names = json.loads(visit.client.preferred_location)
            preferred_location_names = [
            loc.name for loc in Location.query.filter(Location.name.in_(loc_names)).all()
            ]
        except Exception as e:
            print("Error decoding preferred_location:", e)

    # Pass clean location names to template
    return render_template(
        'visit_details.html',
        visit=visit,
        previous_visits=previous_visits,
        preferred_location_names=preferred_location_names
    )

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
            # Fetch previous visits
            previous_visits_query = SiteVisit.query.filter_by(client_id=client.id).order_by(SiteVisit.visit_date.desc()).all()
            previous_visits = []
            
            for visit in previous_visits_query:
                agents_list = []
                if visit.agents_involved:
                    try:
                        agent_ids = json.loads(visit.agents_involved)
                        for agent_id in agent_ids:
                            # Using Session.get() instead of deprecated Query.get()
                            agent = db.session.get(User, agent_id)
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

            # Parse locations stored as JSON arrays of names
            import json
            
            preferred_location_name = None
            if client.preferred_location:
                try:
                    loc_list = json.loads(client.preferred_location)  # e.g., ["Bandra"]
                    if loc_list:
                        preferred_location_name = loc_list[0]
                except json.JSONDecodeError:
                    preferred_location_name = client.preferred_location  # fallback
            
            current_location_name = None
            if client.current_location:
                try:
                    loc_list = json.loads(client.current_location)
                    if loc_list:
                        current_location_name = loc_list[0]
                except json.JSONDecodeError:
                    current_location_name = client.current_location  # fallback

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
                    'preferred_location': preferred_location_name or '',
                    'current_location': current_location_name or '',
                    'profession':client.profession or'',
                    'building_name': client.building_name or '',
                    'preferred_projects': client.preferred_projects or '[]',
                    'notes': client.notes or '',
                    'ethnicity': client.ethnicity or ''
                },
                'previous_visits': previous_visits
            })
        else:
            return jsonify({'exists': False})
    
    # GET request: render form
    projects = Project.query.order_by(Project.name).all()
    users = User.query.filter_by(role='agent').all()
    locations = Location.query.filter_by(is_active=True).all()  # for dropdown if needed
    return render_template('log_visit.html', projects=projects, users=users, locations=locations)


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
        preferred_locations = data.get('preferred_location', [])
        if isinstance(preferred_locations, list):
            preferred_locations_json = json.dumps(preferred_locations)
        else:
            preferred_locations_json = json.dumps([preferred_locations]) if preferred_locations else json.dumps([])
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
                preferred_location=preferred_locations_json,
                current_location=data.get('current_location', ''),
                building_name=data.get('building_name', ''),
                preferred_projects=json.dumps(data.get('preferred_projects', [])),
                notes=data.get('notes', ''),
                ethnicity=data.get('ethnicity', ''),
                profession=data.get('profession', ''),
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
            client.preferred_projects = json.dumps(data.get('preferred_projects', []))
            client.current_location = data.get('current_location', '')
            client.preferred_location = preferred_locations_json
            client.building_name = data.get('building_name', '')
            client.notes = data.get('notes', '')
            client.ethnicity = data.get('ethnicity', '')
            client.profession = data.get('profession', '') 
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




def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload-data', methods=['GET', 'POST'])

def upload_data():
    if request.method == 'GET':
        return render_template('upload_data.html')

    file = request.files.get('file')
    if not file or not allowed_file(file.filename):
        return jsonify({'success': False, 'message': 'Please upload a valid Excel or CSV file.'})

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    try:
        df = pd.read_excel(filepath) if file.filename.endswith(('xls', 'xlsx')) else pd.read_csv(filepath)
        df.fillna('', inplace=True)

        # Load reference tables
        locations = {str(l.id): l.name for l in Location.query.all()}
        projects = {str(p.id): p.name for p in Project.query.all()}
        agents = {str(u.id): u.name for u in User.query.all()}

        def convert_ids_to_names(value, lookup_dict, default_none=False):
            if not value or str(value).strip() == '':
                return ["None"] if default_none else []
            ids = [str(v).strip() for v in str(value).split(',') if str(v).strip()]
            names = [lookup_dict.get(i, f"Unknown-{i}") for i in ids]
            return names

        total_clients, total_visits = 0, 0

        for _, row in df.iterrows():
            name = str(row.get('name', '')).strip()
            mobile = str(row.get('mobile', '')).strip()
            if not name or not mobile:
                continue

            # Convert IDs to names for multi-value fields
            preferred_locations = convert_ids_to_names(row.get('preferred_location', ''), locations)
            preferred_projects_ids = [str(v).strip() for v in str(row.get('preferred_projects', '')).split(',') if str(v).strip()]
            agents_involved_ids = [str(v).strip() for v in str(row.get('agents_involved', '')).split(',') if str(v).strip()]
            telecallers_involved = convert_ids_to_names(row.get('telecallers_involved', ''), agents, default_none=True)
            # Use the existing function, but take only the first name
            lead_source_project_list = convert_ids_to_names(row.get('lead_source_project', ''), projects)
            lead_source_project_name = lead_source_project_list[0] if lead_source_project_list else ""
            current_location_list = convert_ids_to_names(row.get('current_location', ''), locations)
            # Convert current_location ID to name
            current_location_name = current_location_list[0] if current_location_list else ""
            # Add current user automatically (save as ID)
            if str(current_user.id) not in agents_involved_ids:
                agents_involved_ids.append(str(current_user.id))

            # Create or update client
            client = Client.query.filter_by(mobile=mobile).first()
            if not client:
                client = Client(
                    name=name,
                    mobile=mobile,
                    secondary_number=row.get('secondary_number', ''),
                    email=row.get('email', ''),
                    lead_source=row.get('lead_source', ''),
                    lead_source_project=lead_source_project_name,
                    bhk_requirement=row.get('bhk_requirement', ''),
                    budget=row.get('budget', ''),
                    preferred_location=json.dumps(preferred_locations),
                    current_location=current_location_name,
                    building_name=row.get('building_name', ''),
                    preferred_projects=json.dumps(preferred_projects_ids),
                    ethnicity=row.get('ethnicity', ''),
                    profession=row.get('profession', ''),
                    notes=row.get('notes', ''),
                    created_by=current_user.id
                )
                db.session.add(client)
                db.session.flush()
                total_clients += 1
            else:
                client.name = name
                client.secondary_number = row.get('secondary_number', '')
                client.email = row.get('email', '')
                client.lead_source = row.get('lead_source', '')
                client.lead_source_project = lead_source_project_name,
                client.bhk_requirement = row.get('bhk_requirement', '')
                client.budget = row.get('budget', '')
                client.preferred_location = json.dumps(preferred_locations)
                client.current_location = current_location_name
                client.building_name = row.get('building_name', '')
                client.preferred_projects = json.dumps(preferred_projects_ids)
                client.ethnicity = row.get('ethnicity', '')
                client.profession = row.get('profession', '')
                client.notes = row.get('notes', '')

            # Create site visit
            visit_date_str = str(row.get('visit_date', '')).strip()
            project_id = str(row.get('project_id', '')).strip()
            if visit_date_str and project_id:
                try:
                    visit_date = pd.to_datetime(visit_date_str).to_pydatetime()
                    visit = SiteVisit(
                        client_id=client.id,
                        visit_date=visit_date,
                        project_id=int(project_id),
                        status=row.get('status', 'Upcoming'),
                        agents_involved=json.dumps(agents_involved_ids),
                        telecallers_involved=json.dumps(telecallers_involved),
                        notes=row.get('notes', ''),
                        created_by=current_user.id
                    )
                    db.session.add(visit)
                    total_visits += 1
                except Exception:
                    continue

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Successfully uploaded {total_clients} clients and {total_visits} site visits.'
        })

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


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
    
    app.run(debug=True)
