import os
import secrets
import string

from PIL import Image
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
import json
from werkzeug.utils import secure_filename

# Load configuration from file
def load_config():
    config = {
        'UPLOAD_FOLDER': 'uploads',
        'USER_CREDENTIALS_FILE': 'user_credentials.txt',
        'SECRET_KEY': 'your_secret_key_here'
    }
    
    try:
        if os.path.exists('config.txt'):
            with open('config.txt', 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            config[key.strip()] = value.strip()
    except Exception as e:
        print(f"Warning: Could not load config.txt: {e}")
    
    return config

# Check if config has changed and reload if needed
def get_current_upload_folder():
    current_config = load_config()
    new_folder = current_config['UPLOAD_FOLDER']
    
    # Update app config if changed
    if app.config['UPLOAD_FOLDER'] != new_folder:
        app.logger.info(f"Upload folder changed from {app.config['UPLOAD_FOLDER']} to {new_folder}")
        app.config['UPLOAD_FOLDER'] = new_folder
        # Ensure new directory exists
        os.makedirs(new_folder, exist_ok=True)
    
    return app.config['UPLOAD_FOLDER']

config = load_config()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = config['UPLOAD_FOLDER']
# Support all common file types
app.config['ALLOWED_EXTENSIONS'] = {
    # Images
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico', 'tiff', 'tif',
    # Documents
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'rtf', 'odt', 'ods', 'odp',
    # Archives
    'zip', 'rar', '7z', 'tar', 'gz', 'bz2',
    # Audio
    'mp3', 'wav', 'flac', 'aac', 'm4a', 'ogg', 'wma',
    # Video
    'mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm', 'm4v',
    # Code
    'py', 'js', 'html', 'css', 'json', 'xml', 'yaml', 'yml', 'md', 'sh', 'bat',
    # Other
    'csv', 'sql', 'log', 'ini', 'cfg', 'conf'
}
app.config['USER_CREDENTIALS_FILE'] = config['USER_CREDENTIALS_FILE']
app.secret_key = config['SECRET_KEY']
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
            default_hash = generate_password_hash(default_password, method='pbkdf2:sha256')
            
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

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_file_mime_type(filename):
    ext = filename.split('.')[-1].lower()
    mime_types = {
        # Images
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'bmp': 'image/bmp',
        'webp': 'image/webp',
        'svg': 'image/svg+xml',
        'ico': 'image/x-icon',
        'tiff': 'image/tiff',
        'tif': 'image/tiff',
        # Documents
        'pdf': 'application/pdf',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'ppt': 'application/vnd.ms-powerpoint',
        'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'txt': 'text/plain',
        'rtf': 'application/rtf',
        # Archives
        'zip': 'application/zip',
        'rar': 'application/x-rar-compressed',
        '7z': 'application/x-7z-compressed',
        'tar': 'application/x-tar',
        'gz': 'application/gzip',
        # Audio
        'mp3': 'audio/mpeg',
        'wav': 'audio/wav',
        'flac': 'audio/flac',
        'aac': 'audio/aac',
        'm4a': 'audio/mp4',
        'ogg': 'audio/ogg',
        # Video
        'mp4': 'video/mp4',
        'avi': 'video/x-msvideo',
        'mkv': 'video/x-matroska',
        'mov': 'video/quicktime',
        'wmv': 'video/x-ms-wmv',
        'webm': 'video/webm',
        # Code/Text
        'html': 'text/html',
        'css': 'text/css',
        'js': 'application/javascript',
        'json': 'application/json',
        'xml': 'application/xml',
        'csv': 'text/csv',
        'md': 'text/markdown',
    }
    return mime_types.get(ext, 'application/octet-stream')

def get_file_type_category(filename):
    """Categorize file type for icon display"""
    ext = filename.split('.')[-1].lower()
    
    image_exts = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico', 'tiff', 'tif'}
    document_exts = {'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt'}
    spreadsheet_exts = {'xls', 'xlsx', 'csv', 'ods'}
    presentation_exts = {'ppt', 'pptx', 'odp'}
    archive_exts = {'zip', 'rar', '7z', 'tar', 'gz', 'bz2'}
    audio_exts = {'mp3', 'wav', 'flac', 'aac', 'm4a', 'ogg', 'wma'}
    video_exts = {'mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm', 'm4v'}
    code_exts = {'py', 'js', 'html', 'css', 'json', 'xml', 'yaml', 'yml', 'md', 'sh', 'bat', 'sql'}
    
    if ext in image_exts:
        return 'image'
    elif ext in document_exts:
        return 'document'
    elif ext in spreadsheet_exts:
        return 'spreadsheet'
    elif ext in presentation_exts:
        return 'presentation'
    elif ext in archive_exts:
        return 'archive'
    elif ext in audio_exts:
        return 'audio'
    elif ext in video_exts:
        return 'video'
    elif ext in code_exts:
        return 'code'
    else:
        return 'file'

# Increased from default (400,400)
THUMBNAIL_SIZE = (800, 800)  

def create_thumbnail(path):
    try:
        img = Image.open(path)
        img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
        upload_folder = get_current_upload_folder()
        thumb_dir = os.path.join(upload_folder, 'thumbs')
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_path = os.path.join(thumb_dir, os.path.basename(path))
        img.save(thumb_path)
        return thumb_path
    except Exception as e:
        app.logger.error(f"Thumbnail creation failed: {str(e)}")
        return None


# Add pagination parameters to index route
@app.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 50  # Items per page

    # Get sorted files (newest first)
    upload_folder = get_current_upload_folder()
    files = []
    for filename in os.listdir(upload_folder):
        path = os.path.join(upload_folder, filename)
        if allowed_file(filename) and os.path.isfile(path):
            files.append({
                'name': filename,
                'mtime': os.path.getmtime(path),
                'type': get_file_type_category(filename)
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
        files=paginated_files,
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
def serve_file(filename):
    upload_folder = get_current_upload_folder()
    mime_type = get_file_mime_type(filename)
    return send_from_directory(upload_folder, filename, mimetype=mime_type)

@app.route('/thumbs/<filename>')
@login_required
def serve_thumbnail(filename):
    upload_folder = get_current_upload_folder()
    thumb_dir = os.path.join(upload_folder, 'thumbs')
    return send_from_directory(thumb_dir, filename)
    
def calculate_file_hash(file_path):
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

@app.route('/upload', methods=['POST'])
def upload_file():
    # Check if this is an AJAX request for hash verification
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if 'files' not in request.files:
        if is_ajax:
            return json.dumps({'success': False, 'error': 'No file part'}), 400
        flash('No file part', 'error')
        return redirect(url_for('index'))
    
    files = request.files.getlist('files')
    results = []
    success_count = 0
    failure_count = 0

    for file in files:
        if file.filename == '':
            failure_count += 1
            if is_ajax:
                results.append({'filename': '', 'success': False, 'error': 'Empty filename'})
            continue
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            if not filename:
                failure_count += 1
                if is_ajax:
                    results.append({'filename': file.filename, 'success': False, 'error': 'Invalid filename'})
                continue
            
            upload_folder = get_current_upload_folder()
            target_path = os.path.join(upload_folder, filename)
            original_filename = filename
            
            # Handle filename conflicts
            if os.path.exists(target_path):
                base, ext = os.path.splitext(filename)
                counter = 1
                while True:
                    new_filename = f"{base}_{counter}{ext}"
                    new_target = os.path.join(upload_folder, new_filename)
                    if not os.path.exists(new_target):
                        filename = new_filename
                        target_path = new_target
                        break
                    counter += 1
            
            try:
                file.save(target_path)
                
                # Calculate hash for verification
                file_hash = calculate_file_hash(target_path)
                
                success_count += 1
                
                # Generate thumbnail for images
                if filename.lower().endswith(('jpg', 'jpeg', 'png', 'gif')):
                    create_thumbnail(target_path)
                
                if is_ajax:
                    results.append({
                        'filename': original_filename,
                        'saved_as': filename,
                        'success': True,
                        'hash': file_hash
                    })

            except Exception as e:
                app.logger.error(f"Error saving file {filename}: {str(e)}")
                failure_count += 1
                if is_ajax:
                    results.append({
                        'filename': original_filename,
                        'success': False,
                        'error': str(e)
                    })
        else:
            failure_count += 1
            if is_ajax:
                results.append({
                    'filename': file.filename,
                    'success': False,
                    'error': 'File type not allowed'
                })

    # Return JSON for AJAX requests
    if is_ajax:
        return json.dumps({
            'success': failure_count == 0,
            'files': results,
            'success_count': success_count,
            'failure_count': failure_count
        }), 200, {'Content-Type': 'application/json'}
    
    # Traditional form submission
    if success_count > 0:
        flash(f'Successfully uploaded {success_count} file(s)', 'success')
    if failure_count > 0:
        flash(f'Failed to upload {failure_count} file(s)', 'error')

    return redirect(url_for('index'))

@app.route('/delete/<filename>')
def delete_file(filename):
    upload_folder = get_current_upload_folder()
    file_path = os.path.join(upload_folder, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        flash(f'Deleted: {filename}', 'success')
    else:
        flash('File not found', 'error')
    return redirect(url_for('index'))

if __name__ == '__main__':
    load_users()  # Load users at startup
    app.run(host='0.0.0.0', port=80, debug=False)