import os
import secrets
import string

from PIL import Image
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
# app.config['THUMBS_FOLDER'] = 'thumbs'
app.config['ALLOWED_EXTENSIONS'] = {'jpg', 'jpeg', 'png', 'gif', 'b64'}
app.config['USER_CREDENTIALS_FILE'] = 'user_credentials.txt'
app.secret_key = 'your_secret_key_here'
app.config['REMEMBER_COOKIE_DURATION'] = 30 * 24 * 3600  # 30 days


# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id):
        self.id = id

# Load users from file
def load_users():
    users = {}
    try:
        if os.path.exists(app.config['USER_CREDENTIALS_FILE']):
            with open(app.config['USER_CREDENTIALS_FILE'], 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        parts = line.strip().split(':', 1)
                        if len(parts) == 2:
                            username, password_hash = parts
                            users[username] = password_hash
        else:
            # Create default user if file doesn't exist
            default_user = 'admin'
            default_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
            default_hash = generate_password_hash(default_password)
            
            with open(app.config['USER_CREDENTIALS_FILE'], 'w') as f:
                f.write(f"{default_user}:{default_hash}\n")
            
            app.logger.warning(f"Created default user: {default_user} with password: {default_password}")
            users[default_user] = default_hash
    
    except Exception as e:
        app.logger.error(f"Error loading users: {str(e)}")
    
    return users

@login_manager.user_loader
def load_user(user_id):
    users = load_users()
    return User(user_id) if user_id in users else None

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
# os.makedirs(app.config['THUMBS_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_image_mime_type(filename):
    ext = filename.split('.')[-1].lower()
    if ext == 'png':
        return 'image/png'
    elif ext in ['jpg', 'jpeg']:
        return 'image/jpeg'
    elif ext == 'gif':
        return 'image/gif'
    elif ext == 'txt':
        return 'text/plain'
    return 'application/octet-stream'

# Add after allowed_file() function
THUMBNAIL_SIZE = (800, 800)  # Increased from default (400,400)

def create_thumbnail(path):
    try:
        img = Image.open(path)
        img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
        thumb_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'thumbs')
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_path = os.path.join(thumb_dir, os.path.basename(path))
        img.save(thumb_path)
        return thumb_path
    except Exception as e:
        app.logger.error(f"Thumbnail creation failed: {str(e)}")
        return None


# @app.route('/')
# @login_required
# def index():
#     images = os.listdir(app.config['UPLOAD_FOLDER'])
#     return render_template('index.html', images=images)

# Add pagination parameters to index route
@app.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 50  # Items per page

    # Get sorted files (newest first)
    files = []
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if allowed_file(filename) and os.path.isfile(path):
            files.append({
                'name': filename,
                'mtime': os.path.getmtime(path)  # Sort by modified time
            })
    
    # Sort by upload time (newest first)
    files.sort(key=lambda x: x['mtime'], reverse=True)
    
    # Paginate
    total_files = len(files)
    total_pages = (total_files + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    paginated_files = files[start:end]

    return render_template(
        'index.html',
        images=[f['name'] for f in paginated_files],
        page=page,
        total_pages=total_pages,
        total_files=total_files
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = 'remember' in request.form
        
        users = load_users()
        password_hash = users.get(username)
        
        if password_hash and check_password_hash(password_hash, password):
            login_user(User(username), remember=remember)
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        
        flash('Invalid credentials', 'error')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))

@app.route('/uploads/<filename>')
@login_required
def serve_image(filename):
    mime_type = get_image_mime_type(filename)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, mimetype=mime_type)

@app.route('/thumbs/<filename>')
@login_required
def serve_thumbnail(filename):
    thumb_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'thumbs')
    return send_from_directory(thumb_dir, filename)
    
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'files' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('index'))
    
    files = request.files.getlist('files')
    success_count = 0
    failure_count = 0

    for file in files:
        if file.filename == '':
            failure_count += 1
            continue
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            if not filename:
                failure_count += 1
                continue
            
            target_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Handle filename conflicts
            if os.path.exists(target_path):
                base, ext = os.path.splitext(filename)
                counter = 1
                while True:
                    new_filename = f"{base}_{counter}{ext}"
                    new_target = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                    if not os.path.exists(new_target):
                        filename = new_filename
                        target_path = new_target
                        break
                    counter += 1
            
            try:
                file.save(target_path)
                success_count += 1
                    # Generate thumbnail for images
                if filename.lower().endswith(('jpg', 'jpeg', 'png', 'gif')):
                    create_thumbnail(target_path)

            except Exception as e:
                app.logger.error(f"Error saving file {filename}: {str(e)}")
                failure_count += 1
        else:
            failure_count += 1

    # Summary messages
    if success_count > 0:
        flash(f'Successfully uploaded {success_count} file(s)', 'success')
    if failure_count > 0:
        flash(f'Failed to upload {failure_count} file(s). Allowed file types: jpg, jpeg, png, gif, txt', 'error')

    return redirect(url_for('index'))

@app.route('/delete/<filename>')
def delete_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        flash(f'Deleted: {filename}', 'success')
    else:
        flash('File not found', 'error')
    return redirect(url_for('index'))

if __name__ == '__main__':
    load_users()  # Load users at startup
    app.run(host='0.0.0.0', port=80, debug=True)