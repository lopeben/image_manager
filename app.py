import os
import base64
import secrets
import string
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'jpg', 'jpeg', 'png', 'gif'}
app.config['USER_CREDENTIALS_FILE'] = 'user_credentials.txt'
app.secret_key = 'your_secret_key_here'
app.config['REMEMBER_COOKIE_DURATION'] = 30 * 24 * 3600  # 30 days

# Dummy user database (replace with real DB in production)
# users = {
#     "admin": {
#         "password": generate_password_hash("admin_password"),
#         "remember": False
#     }
# }

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

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# New function to get image MIME type
def get_image_mime_type(filename):
    ext = filename.split('.')[-1].lower()
    if ext == 'png':
        return 'image/png'
    elif ext in ['jpg', 'jpeg']:
        return 'image/jpeg'
    elif ext == 'gif':
        return 'image/gif'
    return 'application/octet-stream'

@app.route('/')
@login_required
def index():
    images = os.listdir(app.config['UPLOAD_FOLDER'])
    return render_template('index.html', images=images)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = 'remember' in request.form
        
        user = users.get(username)
        if user and check_password_hash(user['password'], password):
            user['remember'] = remember
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


# New route for base64 image encoding
@app.route('/b64image/<filename>')
@login_required
def serve_image_b64(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.isfile(file_path):
        return jsonify({"error": "File not found"}), 404
    
    try:
        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        
        mime_type = get_image_mime_type(filename)
        return jsonify({
            "filename": filename,
            "mime_type": mime_type,
            "data": f"data:{mime_type};base64,{encoded_string}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/uploads/<filename>')
@login_required
def serve_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('index'))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('index'))
    
    if file and allowed_file(file.filename):
        filename = file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        flash(f'Uploaded: {filename}', 'success')
        return redirect(url_for('index'))
    else:
        flash('Allowed file types: jpg, jpeg, png, gif', 'error')
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
    app.run(host='0.0.0.0', port=80, debug=True)