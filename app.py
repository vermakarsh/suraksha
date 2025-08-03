from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
import mysql.connector
from werkzeug.security import check_password_hash, generate_password_hash
import os
from datetime import datetime
import json
from decimal import Decimal
import pandas as pd
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from config import Config

# Custom JSON encoder for handling datetime, timedelta, and Decimal objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        elif hasattr(obj, 'total_seconds'):
            return obj.total_seconds()
        elif isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def serialize_data(data):
    """Convert data to JSON-serializable format"""
    if isinstance(data, list):
        return [serialize_data(item) for item in data]
    elif isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if hasattr(value, 'isoformat'):
                result[key] = value.isoformat()
            elif hasattr(value, 'total_seconds'):
                result[key] = value.total_seconds()
            elif isinstance(value, Decimal):
                result[key] = float(value)
            else:
                result[key] = value
        return result
    else:
        return data

app = Flask(__name__, static_folder='static', template_folder='templates')

# Load configuration
config = Config()
app.secret_key = config.SECRET_KEY
app.config['SESSION_COOKIE_SECURE'] = config.SESSION_COOKIE_SECURE
app.config['SESSION_COOKIE_HTTPONLY'] = config.SESSION_COOKIE_HTTPONLY  
app.config['SESSION_COOKIE_SAMESITE'] = config.SESSION_COOKIE_SAMESITE

app.json_encoder = CustomJSONEncoder

# Add date filter for templates
@app.template_filter('datetime')
def datetime_filter(date_obj):
    if date_obj:
        return date_obj.strftime('%Y-%m-%d %H:%M')
    return ''

@app.template_filter('date')
def date_filter(date_obj):
    if date_obj:
        return date_obj.strftime('%Y-%m-%d')
    return ''

# Add current date/time to template context
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# Database configuration
DB_CONFIG = {
    'host': config.DB_HOST,
    'user': config.DB_USER,
    'password': config.DB_PASSWORD,
    'database': config.DB_NAME,
    'charset': 'utf8mb4',
    'use_unicode': True
}

def get_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG, autocommit=True)
        return connection
    except mysql.connector.Error as e:
        print(f"Database connection error: {e}")
        return None

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        
        if not all([username, password, role]):
            flash('All fields are required', 'error')
            return render_template('login.html')
        
        connection = get_db_connection()
        if not connection:
            flash('Database connection failed', 'error')
            return render_template('login.html')
        
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s AND role = %s", (username, role))
            user = cursor.fetchone()
            
            # Check both hashed and plain text passwords for compatibility
            password_valid = False
            if user:
                if user['password'].startswith('$') or user['password'].startswith('pbkdf2'):
                    # Hashed password
                    password_valid = check_password_hash(user['password'], password)
                else:
                    # Plain text password (for backward compatibility)
                    password_valid = (user['password'] == password)
            
            if user and password_valid:
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                session['name'] = user['name']
                
                if user['role'] == 'admin':
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('professional_dashboard'))
            else:
                flash('Invalid credentials', 'error')
                
        except mysql.connector.Error as e:
            flash(f'Login error: {e}', 'error')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection failed', 'error')
        return redirect(url_for('login'))
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get all professionals with training counts
        professionals_query = """
            SELECT 
                u.*, 
                COUNT(DISTINCT t.id) as total_trainings,
                COUNT(DISTINCT tr.id) as total_trainees_trained
            FROM users u
            LEFT JOIN trainings t ON u.id = t.conducted_by
            LEFT JOIN trainees tr ON u.id = tr.registered_by
            WHERE u.role = 'professional'
            GROUP BY u.id
            ORDER BY u.name
        """
        cursor.execute(professionals_query)
        professionals = cursor.fetchall()
        
        # Get all trainees with professional names
        trainees_query = """
            SELECT 
                tr.*,
                u.name as registered_by_name
            FROM trainees tr
            LEFT JOIN users u ON tr.registered_by = u.id
            ORDER BY tr.name
        """
        cursor.execute(trainees_query)
        trainees = cursor.fetchall()
        
        # Get all trainings with professional names
        trainings_query = """
            SELECT 
                t.*,
                u.name as conducted_by_name
            FROM trainings t
            LEFT JOIN users u ON t.conducted_by = u.id
            ORDER BY t.training_date DESC
        """
        cursor.execute(trainings_query)
        trainings = cursor.fetchall()
        
        # Serialize data for JSON usage in templates
        professionals_serialized = serialize_data(professionals)
        trainees_serialized = serialize_data(trainees)
        trainings_serialized = serialize_data(trainings)
        
        return render_template('admin_dashboard.html', 
                             professionals=professionals_serialized, 
                             trainees=trainees_serialized, 
                             trainings=trainings_serialized)
        
    except mysql.connector.Error as e:
        flash(f'Database error: {e}', 'error')
        return redirect(url_for('login'))
    finally:
        cursor.close()
        connection.close()

@app.route('/professional')
def professional_dashboard():
    if 'user_id' not in session or session.get('role') != 'professional':
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection failed', 'error')
        return redirect(url_for('login'))
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get trainees registered by this professional
        trainees_query = """
            SELECT * FROM trainees 
            WHERE registered_by = %s 
            ORDER BY name
        """
        cursor.execute(trainees_query, (session['user_id'],))
        trainees = cursor.fetchall()
        
        # Get trainings conducted by this professional
        trainings_query = """
            SELECT * FROM trainings 
            WHERE conducted_by = %s 
            ORDER BY training_date DESC
        """
        cursor.execute(trainings_query, (session['user_id'],))
        trainings = cursor.fetchall()
        
        # Serialize data for JSON usage in templates
        trainees_serialized = serialize_data(trainees)
        trainings_serialized = serialize_data(trainings)
        
        return render_template('professional_dashboard.html', 
                             trainees=trainees_serialized, 
                             trainings=trainings_serialized)
        
    except mysql.connector.Error as e:
        flash(f'Database error: {e}', 'error')
        return redirect(url_for('login'))
    finally:
        cursor.close()
        connection.close()

@app.route('/data')
def data_viewer():
    """Database viewer page showing all tables"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # Get the table parameter from URL
    table = request.args.get('table', 'users')
    
    connection = get_db_connection()
    if not connection:
        flash('Database connection failed', 'error')
        return redirect(url_for('login'))
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get all table data based on selected table
        tables_data = {}
        
        if table == 'users':
            cursor.execute("SELECT * FROM users ORDER BY id DESC")
            tables_data['users'] = cursor.fetchall()
        elif table == 'trainees':
            cursor.execute("""
                SELECT t.*, u.name as registered_by_name 
                FROM trainees t 
                LEFT JOIN users u ON t.registered_by = u.id 
                ORDER BY t.id DESC
            """)
            tables_data['trainees'] = cursor.fetchall()
        elif table == 'trainings':
            cursor.execute("""
                SELECT tr.*, u.name as conducted_by_name 
                FROM trainings tr 
                LEFT JOIN users u ON tr.conducted_by = u.id 
                ORDER BY tr.id DESC
            """)
            tables_data['trainings'] = cursor.fetchall()
        else:
            # Default to users table
            cursor.execute("SELECT * FROM users ORDER BY id DESC")
            tables_data['users'] = cursor.fetchall()
            table = 'users'
        
        # Get table counts for dashboard
        cursor.execute("SELECT COUNT(*) as count FROM users")
        users_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM trainees")
        trainees_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM trainings")
        trainings_count = cursor.fetchone()['count']
        
        # Get professionals for the training edit form
        cursor.execute("SELECT id, name FROM users WHERE role = 'professional' ORDER BY name")
        professionals = cursor.fetchall()
        
        return render_template('data_viewer.html', 
                             tables_data=tables_data,
                             current_table=table,
                             users_count=users_count,
                             trainees_count=trainees_count,
                             trainings_count=trainings_count,
                             professionals=professionals)
        
    except mysql.connector.Error as e:
        flash(f'Database error: {e}', 'error')
        return redirect(url_for('login'))
    finally:
        cursor.close()
        connection.close()

# API Endpoints (same as React backend)

@app.route('/api/users', methods=['GET'])
def get_users():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users ORDER BY id DESC")
        users = cursor.fetchall()
        return jsonify({'success': True, 'users': users})
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/users', methods=['POST'])
def add_user():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        
        # Check if username already exists
        cursor.execute("SELECT id FROM users WHERE username = %s", (data['username'],))
        if cursor.fetchone():
            return jsonify({'error': 'Username already exists'}), 400
        
        # Hash the password
        hashed_password = generate_password_hash(data['password'])
        
        query = """
            INSERT INTO users (name, username, password, mobile_number, gender, age, 
                             designation, department, role)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            data['name'],
            data['username'],
            hashed_password,
            data.get('mobile_number', ''),
            data['gender'],
            data['age'],
            data.get('designation', ''),
            data.get('department', ''),
            data['role']
        ))
        
        return jsonify({'success': True, 'message': 'User added successfully'})
        
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Prevent admin from deleting themselves
    if user_id == session['user_id']:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        
        # Delete related data first
        cursor.execute("DELETE FROM trainings WHERE conducted_by = %s", (user_id,))
        cursor.execute("UPDATE trainees SET registered_by = NULL WHERE registered_by = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        
        return jsonify({'success': True, 'message': 'User deleted successfully'})
        
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

# Individual record endpoints for editing
@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        return jsonify({'success': True, 'data': user})
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        
        # Build update query dynamically
        update_fields = []
        values = []
        
        for field in ['name', 'username', 'mobile_number', 'role', 'gender', 'age', 'department', 'designation']:
            if field in data:
                update_fields.append(f"{field} = %s")
                values.append(data[field])
        
        # Handle password separately
        if 'password' in data and data['password']:
            update_fields.append("password = %s")
            values.append(data['password'])
        
        if not update_fields:
            return jsonify({'error': 'No valid fields to update'}), 400
        
        values.append(user_id)
        query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
        
        cursor.execute(query, values)
        connection.commit()
        
        return jsonify({'success': True, 'message': 'User updated successfully'})
        
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/trainees/<int:trainee_id>', methods=['GET'])
def get_trainee(trainee_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM trainees WHERE id = %s", (trainee_id,))
        trainee = cursor.fetchone()
        
        if not trainee:
            return jsonify({'error': 'Trainee not found'}), 404
            
        return jsonify({'success': True, 'data': trainee})
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/trainees/<int:trainee_id>', methods=['PUT'])
def update_trainee(trainee_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        
        cursor.execute("""
            UPDATE trainees SET 
                name = %s, mobile_number = %s, gender = %s, age = %s,
                department = %s, designation = %s, address = %s, block = %s,
                training_date = %s, cpr_training = %s, first_aid_kit_given = %s,
                life_saving_skills = %s
            WHERE id = %s
        """, (
            data.get('name'), data.get('mobile_number'), data.get('gender'),
            data.get('age'), data.get('department'), data.get('designation'),
            data.get('address'), data.get('block'), data.get('training_date'),
            data.get('cpr_training', False), data.get('first_aid_kit_given', False),
            data.get('life_saving_skills', False), trainee_id
        ))
        
        connection.commit()
        return jsonify({'success': True, 'message': 'Trainee updated successfully'})
        
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/trainings/<int:training_id>', methods=['GET'])
def get_training(training_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM trainings WHERE id = %s", (training_id,))
        training = cursor.fetchone()
        
        if not training:
            return jsonify({'error': 'Training not found'}), 404
            
        return jsonify({'success': True, 'data': training})
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/trainings/<int:training_id>', methods=['PUT'])
def update_training(training_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        
        cursor.execute("""
            UPDATE trainings SET 
                title = %s, training_topic = %s, description = %s, address = %s,
                block = %s, training_date = %s, training_time = %s,
                duration_hours = %s, trainees = %s, status = %s, conducted_by = %s
            WHERE id = %s
        """, (
            data.get('title'), data.get('training_topic'), data.get('description'),
            data.get('address'), data.get('block'), data.get('training_date'),
            data.get('training_time'), data.get('duration_hours'),
            data.get('trainees'), data.get('status'), data.get('conducted_by'), training_id
        ))
        
        connection.commit()
        return jsonify({'success': True, 'message': 'Training updated successfully'})
        
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/professionals', methods=['GET'])
def get_professionals():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE role = 'professional' ORDER BY name")
        professionals = cursor.fetchall()
        return jsonify({'success': True, 'professionals': professionals})
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/professionals', methods=['POST'])
def add_professional():
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        
        # Check if username already exists
        cursor.execute("SELECT id FROM users WHERE username = %s", (data['username'],))
        if cursor.fetchone():
            return jsonify({'error': 'Username already exists'}), 400
        
        # Hash the mobile number as password
        hashed_password = generate_password_hash(data['mobile_number'])
        
        query = """
            INSERT INTO users (name, username, password, mobile_number, gender, age, 
                             designation, department, specialization, experience_years, role)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'professional')
        """
        cursor.execute(query, (
            data['name'],
            data['username'],
            hashed_password,
            data['mobile_number'],
            data['gender'],
            data['age'],
            data.get('designation', ''),
            data.get('department', ''),
            data.get('specialization', ''),
            data.get('experience_years', 0)
        ))
        
        return jsonify({'success': True, 'message': 'Professional added successfully'})
        
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/professionals/<int:prof_id>', methods=['PUT'])
def update_professional(prof_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        query = """
            UPDATE users SET name = %s, username = %s, mobile_number = %s, 
                           gender = %s, age = %s, designation = %s, 
                           department = %s, specialization = %s, experience_years = %s
            WHERE id = %s AND role = 'professional'
        """
        cursor.execute(query, (
            data['name'],
            data['username'],
            data['mobile_number'],
            data['gender'],
            data['age'],
            data.get('designation', ''),
            data.get('department', ''),
            data.get('specialization', ''),
            data.get('experience_years', 0),
            prof_id
        ))
        
        return jsonify({'success': True, 'message': 'Professional updated successfully'})
        
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/professionals/<int:prof_id>', methods=['DELETE'])
def delete_professional(prof_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        
        # Delete related data first
        cursor.execute("DELETE FROM trainings WHERE conducted_by = %s", (prof_id,))
        cursor.execute("UPDATE trainees SET registered_by = NULL WHERE registered_by = %s", (prof_id,))
        cursor.execute("DELETE FROM users WHERE id = %s AND role = 'professional'", (prof_id,))
        
        return jsonify({'success': True, 'message': 'Professional deleted successfully'})
        
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/trainees', methods=['GET'])
def get_trainees():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = request.args.get('user_id')
    user_role = request.args.get('user_role')
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        if user_role == 'admin':
            cursor.execute("SELECT * FROM trainees ORDER BY name")
        else:
            cursor.execute("SELECT * FROM trainees WHERE registered_by = %s ORDER BY name", (user_id,))
        
        trainees = cursor.fetchall()
        return jsonify({'success': True, 'trainees': trainees})
        
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/trainees', methods=['POST'])
def register_trainee():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        
        query = """
            INSERT INTO trainees (name, mobile_number, gender, age, department, designation,
                                address, block, training_date, cpr_training, first_aid_kit_given,
                                life_saving_skills, registered_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            data['name'],
            data.get('mobile_number', ''),
            data['gender'],
            data['age'],
            data['department'],
            data.get('designation', ''),
            data['address'],
            data['block'],
            data['training_date'],
            data.get('cpr_training', False),
            data.get('first_aid_kit_given', False),
            data.get('life_saving_skills', False),
            data['registered_by']
        ))
        
        return jsonify({'success': True, 'message': 'Trainee registered successfully'})
        
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/trainees/<int:trainee_id>', methods=['DELETE'])
def delete_trainee(trainee_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        
        # Check authorization
        if session.get('role') != 'admin':
            cursor.execute("SELECT registered_by FROM trainees WHERE id = %s", (trainee_id,))
            trainee = cursor.fetchone()
            if not trainee or trainee[0] != session['user_id']:
                return jsonify({'error': 'Unauthorized to delete this trainee'}), 401
        
        cursor.execute("DELETE FROM trainees WHERE id = %s", (trainee_id,))
        
        return jsonify({'success': True, 'message': 'Trainee deleted successfully'})
        
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/trainings', methods=['GET'])
def get_trainings():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = request.args.get('user_id')
    user_role = request.args.get('user_role')
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        if user_role == 'admin':
            cursor.execute("SELECT * FROM trainings ORDER BY training_date DESC")
        else:
            cursor.execute("SELECT * FROM trainings WHERE conducted_by = %s ORDER BY training_date DESC", (user_id,))
        
        trainings = cursor.fetchall()
        return jsonify({'success': True, 'trainings': trainings})
        
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/trainings', methods=['POST'])
def create_training():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        
        query = """
            INSERT INTO trainings (title, description, training_topic, address, block,
                                 training_date, training_time, duration_hours, trainees,
                                 status, conducted_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            data['title'],
            data.get('description', ''),
            data['training_topic'],
            data['address'],
            data['block'],
            data['training_date'],
            data['training_time'],
            data['duration_hours'],
            data.get('trainees', 0),
            data.get('status', 'Planned'),
            data['conducted_by']
        ))
        
        return jsonify({'success': True, 'message': 'Training created successfully'})
        
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/api/trainings/<int:training_id>', methods=['DELETE'])
def delete_training(training_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor()
        
        # Check authorization
        if session.get('role') != 'admin':
            cursor.execute("SELECT conducted_by FROM trainings WHERE id = %s", (training_id,))
            training = cursor.fetchone()
            if not training or training[0] != session['user_id']:
                return jsonify({'error': 'Unauthorized to delete this training'}), 401
        
        cursor.execute("DELETE FROM trainings WHERE id = %s", (training_id,))
        
        return jsonify({'success': True, 'message': 'Training deleted successfully'})
        
    except mysql.connector.Error as e:
        return jsonify({'error': f'Database error: {e}'}), 500
    finally:
        cursor.close()
        connection.close()

# Export routes for Excel and PDF
@app.route('/export/excel/<table_name>')
def export_excel(table_name):
    """Export table data to Excel format"""
    if not session.get('user_id') or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized access'}), 403
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Validate table name
        valid_tables = ['users', 'trainees', 'trainings']
        if table_name not in valid_tables:
            return jsonify({'error': 'Invalid table name'}), 400
        
        # Get data based on table
        if table_name == 'users':
            cursor.execute("""
                SELECT id, name, username, role, mobile_number, gender, age, 
                       department, designation, specialization, experience_years, 
                       created_at
                FROM users 
                ORDER BY created_at DESC
            """)
        elif table_name == 'trainees':
            cursor.execute("""
                SELECT id, name, mobile_number, gender, age, department, 
                       designation, address, block, training_date, 
                       cpr_training, first_aid_kit_given, life_saving_skills, 
                       created_at
                FROM trainees 
                ORDER BY created_at DESC
            """)
        else:  # trainings
            cursor.execute("""
                SELECT id, title, training_topic, description, address, block, 
                       training_date, training_time, duration_hours, trainees, 
                       created_at, updated_at
                FROM trainings 
                ORDER BY created_at DESC
            """)
        
        data = cursor.fetchall()
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Format datetime columns
        for col in df.columns:
            if 'date' in col.lower() or 'created_at' in col or 'updated_at' in col:
                if not df[col].empty and df[col].notna().any():
                    df[col] = pd.to_datetime(df[col]).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=table_name.title(), index=False)
            
            # Get the workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets[table_name.title()]
            
            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        
        filename = f"suraksha_{table_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'error': f'Export failed: {str(e)}'}), 500
    finally:
        cursor.close()
        connection.close()

@app.route('/export/pdf/<table_name>')
def export_pdf(table_name):
    """Export table data to PDF format"""
    if not session.get('user_id') or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized access'}), 403
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Validate table name
        valid_tables = ['users', 'trainees', 'trainings']
        if table_name not in valid_tables:
            return jsonify({'error': 'Invalid table name'}), 400
        
        # Get data based on table
        if table_name == 'users':
            cursor.execute("""
                SELECT name, username, role, mobile_number, gender, age, 
                       department, designation, specialization
                FROM users 
                ORDER BY created_at DESC
            """)
            headers = ['Name', 'Username', 'Role', 'Mobile', 'Gender', 'Age', 
                      'Department', 'Designation', 'Specialization']
        elif table_name == 'trainees':
            cursor.execute("""
                SELECT name, mobile_number, gender, age, department, 
                       address, block, training_date, cpr_training, 
                       first_aid_kit_given
                FROM trainees 
                ORDER BY created_at DESC
            """)
            headers = ['Name', 'Mobile', 'Gender', 'Age', 'Department', 
                      'Address', 'Block', 'Training Date', 'CPR', 'First Aid']
        else:  # trainings
            cursor.execute("""
                SELECT title, training_topic, address, block, training_date, 
                       training_time, duration_hours, trainees
                FROM trainings 
                ORDER BY created_at DESC
            """)
            headers = ['Title', 'Topic', 'Address', 'Block', 'Date', 
                      'Time', 'Duration (hrs)', 'Trainees']
        
        data = cursor.fetchall()
        
        # Create PDF in memory
        output = BytesIO()
        doc = SimpleDocTemplate(output, pagesize=A4)
        elements = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=20,
            alignment=1  # Center alignment
        )
        
        # Add title
        title = f"SURAKSHA - {table_name.title()} Report"
        elements.append(Paragraph(title, title_style))
        elements.append(Spacer(1, 20))
        
        # Add generation date
        date_text = f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        elements.append(Paragraph(date_text, styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Prepare table data
        table_data = [headers]
        for row in data:
            formatted_row = []
            for value in row.values():
                if value is None:
                    formatted_row.append('')
                elif isinstance(value, bool):
                    formatted_row.append('Yes' if value else 'No')
                elif isinstance(value, datetime):
                    formatted_row.append(value.strftime('%Y-%m-%d'))
                else:
                    formatted_row.append(str(value))
            table_data.append(formatted_row)
        
        # Create table
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        
        # Build PDF
        doc.build(elements)
        output.seek(0)
        
        filename = f"suraksha_{table_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'error': f'PDF export failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(
        host=config.HOST, 
        port=config.PORT, 
        debug=config.DEBUG
    )
