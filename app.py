import os
import shutil
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, send_from_directory, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'user_uploads'
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_PDF_EXTENSIONS = {'pdf'}
ALLOWED_DOC_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24).hex()
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///students.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    achievements = db.Column(db.Text, default='')
    goals = db.Column(db.Text, default='')
    ambitions = db.Column(db.Text, default='')
    is_admin = db.Column(db.Boolean, default=False)
    terms_accepted = db.Column(db.Boolean, default=False)
    terms_accepted_at = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80))
    message = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

@app.before_request
def create_tables():
    db.create_all()

def allowed_file(filename, allowed):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed

def user_folder(user_id, sub=''):
    folder = os.path.join(app.config['UPLOAD_FOLDER'], str(user_id), sub)
    os.makedirs(folder, exist_ok=True)
    return folder

base_template = '''
<!DOCTYPE html>
<html lang="en" data-bs-theme="light">
<head>
    <meta charset="UTF-8">
    <title>ScholarSpace - Student Portal</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
    <style>
        :root {
            --primary-color: #4a90e2;
            --hover-color: #357abd;
            --success-color: #28a745;
            --danger-color: #dc3545;
        }
        body {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            min-height: 100vh;
        }
        .auth-card {
            max-width: 400px;
            margin: 2rem auto;
            border: none;
            border-radius: 15px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            overflow: hidden;
            background: white;
        }
        .auth-header {
            background: var(--primary-color);
            color: white;
            padding: 1.5rem;
            text-align: center;
        }
        .auth-body {
            padding: 2rem;
        }
        .chat-bubble {
            background: var(--primary-color);
            color: white;
            border-radius: 15px;
            padding: 0.75rem 1.25rem;
            margin: 0.5rem 0;
            max-width: 80%;
            animation: fadeIn 0.3s ease-in;
            transition: transform 0.2s ease;
        }
        .chat-bubble.user {
            background: var(--success-color);
            margin-left: auto;
        }
        .chat-bubble:hover {
            transform: translateX(5px);
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .upload-preview {
            border: 2px dashed #dee2e6;
            border-radius: 10px;
            padding: 1rem;
            text-align: center;
            transition: border-color 0.3s ease;
        }
        .upload-preview:hover {
            border-color: var(--primary-color);
        }
        .navbar-brand {
            font-weight: 600;
            letter-spacing: 0.5px;
        }
        .feature-icon {
            width: 50px;
            height: 50px;
            background: var(--primary-color);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            margin: 1rem auto;
        }
        .admin-section { background: #ffe; padding: 10px; border-radius: 6px; margin-bottom: 20px;}
        .delete-btn { color: #fff; background: #c00; border: none; border-radius: 4px; padding: 2px 8px; font-size: 0.9em;}
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary shadow-sm">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('home') }}">
                <i class="bi bi-journal-bookmark-fill me-2"></i>ScholarSpace
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <div class="navbar-nav ms-auto">
                    {% if session.user_id %}
                        <a href="{{ url_for('profile') }}" class="nav-link"><i class="bi bi-person-circle me-1"></i>Profile</a>
                        <a href="{{ url_for('achievements') }}" class="nav-link"><i class="bi bi-trophy me-1"></i>Achievements</a>
                        <a href="{{ url_for('notes') }}" class="nav-link"><i class="bi bi-journal-text me-1"></i>Notes</a>
                        <a href="{{ url_for('personal_documents') }}" class="nav-link"><i class="bi bi-folder me-1"></i>Personal Docs</a>
                        <a href="{{ url_for('chat') }}" class="nav-link"><i class="bi bi-chat-dots me-1"></i>Chat</a>
                        {% if session.is_admin %}
                            <a href="{{ url_for('admin_panel') }}" class="nav-link text-warning"><i class="bi bi-shield-lock me-1"></i>Admin</a>
                        {% endif %}
                        <a href="{{ url_for('logout') }}" class="nav-link"><i class="bi bi-box-arrow-right me-1"></i>Logout</a>
                    {% else %}
                        <a href="{{ url_for('login') }}" class="nav-link"><i class="bi bi-box-arrow-in-right me-1"></i>Login</a>
                        <a href="{{ url_for('register') }}" class="nav-link"><i class="bi bi-person-plus me-1"></i>Register</a>
                    {% endif %}
                </div>
            </div>
        </div>
    </nav>
    <main class="container py-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="flashes">
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }} alert-dismissible fade show">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        {{ content|safe }}
    </main>
    <footer class="bg-primary text-white mt-auto">
        <div class="container py-3 text-center">
            <small>&copy; 2024 ScholarSpace. All rights reserved.</small>
        </div>
    </footer>
    <script src="https://cdn.socket.io/4.3.2/socket.io.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    {{ custom_js|safe }}
</body>
</html>
'''

def render_page(content, custom_js='', **kwargs):
    return render_template_string(base_template, content=content, custom_js=custom_js, **kwargs)

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    content = f'''
    <div class="text-center py-5">
        <div class="feature-icon"><i class="bi bi-stars fs-1"></i></div>
        <h2>Welcome, {user.username}!</h2>
        <p class="lead">This is your student portal. Use the navigation bar to access your profile, achievements, notes, documents, and chat room.</p>
    </div>
    '''
    return render_page(content)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        terms = request.form.get('terms')
        if not username or not email or not password:
            flash('All fields are required!', 'danger')
            return redirect(url_for('register'))
        if not email.endswith('@gmail.com'):
            flash('Only Gmail addresses are allowed!', 'danger')
            return redirect(url_for('register'))
        if not terms:
            flash('You must accept the terms and conditions', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))
        is_admin = False
        if username.lower() == 'admin' and not User.query.filter_by(is_admin=True).first():
            is_admin = True
        user = User(
            username=username,
            email=email,
            is_admin=is_admin,
            terms_accepted=True,
            terms_accepted_at=datetime.utcnow()
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    content = '''
    <div class="auth-card">
        <div class="auth-header">
            <h2><i class="bi bi-person-plus"></i> Create Account</h2>
        </div>
        <div class="auth-body">
            <form method="POST">
                <div class="mb-3">
                    <label class="form-label">Username</label>
                    <input type="text" name="username" class="form-control form-control-lg" required>
                </div>
                <div class="mb-3">
                    <label class="form-label">Email (Gmail only)</label>
                    <input type="email" name="email" class="form-control form-control-lg" required>
                </div>
                <div class="mb-3">
                    <label class="form-label">Password</label>
                    <input type="password" name="password" class="form-control form-control-lg" required>
                </div>
                <div class="mb-3 form-check">
                    <input type="checkbox" name="terms" class="form-check-input" required>
                    <label class="form-check-label">
                        I agree to the <a href="/terms" target="_blank">Terms of Service</a>
                    </label>
                </div>
                <button type="submit" class="btn btn-primary btn-lg w-100">
                    <i class="bi bi-person-check"></i> Register
                </button>
            </form>
            <div class="text-center mt-3">
                Already have an account? <a href="{{ url_for('login') }}">Login here</a>
            </div>
        </div>
    </div>
    '''
    return render_page(content)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_id = request.form['login_id'].strip().lower()
        password = request.form['password']
        user = User.query.filter((User.username == login_id) | (User.email == login_id)).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['is_admin'] = user.is_admin
            return redirect(url_for('home'))
        flash('Invalid username/email or password!', 'danger')
    content = '''
    <div class="auth-card">
        <div class="auth-header">
            <h2><i class="bi bi-box-arrow-in-right"></i> Welcome Back</h2>
        </div>
        <div class="auth-body">
            <form method="POST">
                <div class="mb-3">
                    <label class="form-label">Username/Email</label>
                    <input type="text" name="login_id" class="form-control form-control-lg" required>
                </div>
                <div class="mb-3">
                    <label class="form-label">Password</label>
                    <div class="input-group">
                        <input type="password" name="password" class="form-control form-control-lg" required>
                        <button class="btn btn-outline-secondary" type="button" id="togglePassword">
                            <i class="bi bi-eye"></i>
                        </button>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary btn-lg w-100">
                    <i class="bi bi-box-arrow-in-right"></i> Login
                </button>
            </form>
            <div class="text-center mt-3">
                <a href="{{ url_for('forgot') }}" class="text-muted">Forgot account?</a>
            </div>
        </div>
    </div>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('togglePassword').addEventListener('click', function() {
                const passwordInput = document.querySelector('input[name="password"]');
                const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
                passwordInput.setAttribute('type', type);
                this.querySelector('i').classList.toggle('bi-eye');
                this.querySelector('i').classList.toggle('bi-eye-slash');
            });
        });
    </script>
    '''
    return render_page(content)

@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    msg = ''
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            msg = f"Your username is: <b>{user.username}</b>. Please contact admin to reset your password."
        else:
            msg = "No account found with that email."
    content = f'''
    <div class="auth-card">
        <div class="auth-header">
            <h2><i class="bi bi-question-circle"></i> Account Recovery</h2>
        </div>
        <div class="auth-body">
            <form method="POST">
                <div class="mb-3">
                    <label class="form-label">Enter your Gmail address:</label>
                    <input type="email" name="email" class="form-control form-control-lg" required>
                </div>
                <button type="submit" class="btn btn-primary btn-lg w-100">Recover</button>
            </form>
            <div class="mt-3">{msg}</div>
        </div>
    </div>
    '''
    return render_page(content)

@app.route('/terms')
def terms():
    content = '''
    <div class="card shadow mx-auto" style="max-width:700px;">
        <div class="card-header bg-primary text-white">
            <h2><i class="bi bi-file-earmark-text"></i> Terms and Conditions</h2>
        </div>
        <div class="card-body" style="max-height: 400px; overflow-y: auto;">
            <h4>1. Acceptance of Terms</h4>
            <p>By using this site, you agree to abide by these terms and conditions. If you do not agree, do not use the site.</p>
            <h4>2. Privacy</h4>
            <p>Your achievements, notes, and documents are private and only visible to you and site administrators.</p>
            <h4>3. Content</h4>
            <p>Do not upload inappropriate or illegal content. Admins may remove content or users at their discretion.</p>
            <h4>4. Security</h4>
            <p>Keep your password safe. If you forget your password, use your Gmail to recover your username and contact admin for reset.</p>
            <h4>5. Changes</h4>
            <p>Terms may change at any time. Continued use means you accept the latest terms.</p>
        </div>
    </div>
    '''
    return render_page(content)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('is_admin', None)
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        user.achievements = request.form['achievements']
        user.goals = request.form['goals']
        user.ambitions = request.form['ambitions']
        db.session.commit()
        flash('Profile updated!', 'success')
    content = f'''
    <div class="card shadow mx-auto" style="max-width:600px;">
        <div class="card-header bg-primary text-white">
            <h2><i class="bi bi-person-circle"></i> Profile</h2>
        </div>
        <div class="card-body">
            <form method="POST">
                <div class="mb-3">
                    <label class="form-label">Achievements (text only):</label>
                    <textarea name="achievements" class="form-control" rows="2">{user.achievements}</textarea>
                </div>
                <div class="mb-3">
                    <label class="form-label">Goals:</label>
                    <textarea name="goals" class="form-control" rows="2">{user.goals}</textarea>
                </div>
                <div class="mb-3">
                    <label class="form-label">Ambitions:</label>
                    <textarea name="ambitions" class="form-control" rows="2">{user.ambitions}</textarea>
                </div>
                <button type="submit" class="btn btn-primary">Save</button>
            </form>
        </div>
    </div>
    '''
    return render_page(content)

@app.route('/achievements', methods=['GET', 'POST'])
def achievements():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    img_filename = None
    img_path = None
    user_img_folder = user_folder(user_id)
    for fname in os.listdir(user_img_folder):
        if fname.startswith('achievement.') and allowed_file(fname, ALLOWED_IMAGE_EXTENSIONS):
            img_filename = fname
            img_path = url_for('uploaded_file', user_id=user_id, filename=img_filename)
            break
    if request.method == 'POST':
        if 'achievement_img' in request.files:
            file = request.files['achievement_img']
            if file and allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f'achievement.{ext}'
                filepath = os.path.join(user_img_folder, filename)
                for fname in os.listdir(user_img_folder):
                    if fname.startswith('achievement.'):
                        os.remove(os.path.join(user_img_folder, fname))
                file.save(filepath)
                img_filename = filename
                img_path = url_for('uploaded_file', user_id=user_id, filename=img_filename)
                flash('Achievement image uploaded!', 'success')
            else:
                flash('Invalid image file!', 'danger')
    content = '''
    <div class="card shadow mx-auto" style="max-width:900px;">
        <div class="card-header bg-primary text-white">
            <h2><i class="bi bi-trophy"></i> Achievements</h2>
        </div>
        <div class="card-body">
            <form method="POST" enctype="multipart/form-data">
                <label class="form-label">Upload an image of your achievement:</label>
                <input type="file" name="achievement_img" accept="image/*" class="form-control mb-2">
                <button type="submit" class="btn btn-primary mb-2">Upload</button>
            </form>
    '''
    if img_path:
        content += f'''
            <div class="w-100" style="height:60vh;max-height:70vw;overflow:hidden;">
                <label>Your achievement image:</label><br>
                <img src="{img_path}" style="width:100%;height:100%;object-fit:cover;display:block;">
            </div>
        '''
    content += '</div></div>'
    return render_page(content)


@app.route('/notes', methods=['GET', 'POST'])
def notes():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    user_notes_folder = user_folder(user_id)
    pdf_files = [f for f in os.listdir(user_notes_folder) if allowed_file(f, ALLOWED_PDF_EXTENSIONS)]
    if request.method == 'POST':
        if 'note_pdf' in request.files:
            file = request.files['note_pdf']
            if file and allowed_file(file.filename, ALLOWED_PDF_EXTENSIONS):
                filename = secure_filename(file.filename)
                filepath = os.path.join(user_notes_folder, filename)
                file.save(filepath)
                pdf_files.append(filename)
                flash('PDF note uploaded!', 'success')
            else:
                flash('Invalid PDF file!', 'danger')
    pdf_files = list(set(pdf_files))
    content = '''
    <div class="card shadow mx-auto" style="max-width:600px;">
        <div class="card-header bg-primary text-white">
            <h2><i class="bi bi-journal-text"></i> Notes</h2>
        </div>
        <div class="card-body">
            <form method="POST" enctype="multipart/form-data">
                <label class="form-label">Upload your notes (PDF only):</label>
                <input type="file" name="note_pdf" accept="application/pdf" class="form-control mb-2">
                <button type="submit" class="btn btn-primary mb-2">Upload</button>
            </form>
    '''
    if pdf_files:
        content += '<div><label>Your uploaded notes:</label>'
        for pdf in pdf_files:
            link = url_for('uploaded_file', user_id=session['user_id'], filename=pdf)
            content += f'<a class="pdf-link" href="{link}" target="_blank">{pdf}</a>'
        content += '</div>'
    content += '</div></div>'
    return render_page(content)

@app.route('/personal_documents', methods=['GET', 'POST'])
def personal_documents():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    doc_folder = user_folder(user_id, 'documents')
    if request.method == 'POST':
        if 'document' in request.files:
            file = request.files['document']
            if file and allowed_file(file.filename, ALLOWED_DOC_EXTENSIONS):
                filename = secure_filename(file.filename)
                file.save(os.path.join(doc_folder, filename))
                flash('Document uploaded successfully', 'success')
            else:
                flash('Invalid file type!', 'danger')
    documents = os.listdir(doc_folder)
    content = '''
    <div class="card shadow mx-auto" style="max-width:600px;">
        <div class="card-header bg-primary text-white">
            <h2><i class="bi bi-folder"></i> Personal Documents</h2>
        </div>
        <div class="card-body">
            <form method="POST" enctype="multipart/form-data">
                <div class="mb-3">
                    <label class="form-label">Upload Document (PDF/DOC/TXT):</label>
                    <input type="file" name="document" class="form-control" accept=".pdf,.doc,.docx,.txt" required>
                </div>
                <button type="submit" class="btn btn-primary">Upload</button>
            </form>
            <h3 class="mt-4 fs-5">Your Documents</h3>
            <div class="list-group">
    '''
    for doc in documents:
        doc_url = url_for('serve_document', user_id=user_id, filename=doc)
        content += f'''
        <div class="list-group-item d-flex justify-content-between align-items-center">
            <a href="{doc_url}" target="_blank">{doc}</a>
            <form method="POST" action="{url_for('delete_document', filename=doc)}" style="display:inline;">
                <button type="submit" class="btn btn-danger btn-sm">Delete</button>
            </form>
        </div>
        '''
    content += '</div></div></div>'
    return render_page(content)

@app.route('/documents/<user_id>/<filename>')
def serve_document(user_id, filename):
    if 'user_id' not in session:
        abort(403)
    if str(session['user_id']) != user_id and not session.get('is_admin'):
        abort(403)
    return send_from_directory(user_folder(user_id, 'documents'), filename)

@app.route('/delete_document/<filename>', methods=['POST'])
def delete_document(filename):
    user_id = session['user_id']
    file_path = os.path.join(user_folder(user_id, 'documents'), filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        flash('Document deleted successfully', 'success')
    return redirect(url_for('personal_documents'))

@app.route('/chat', methods=['GET'])
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    content = '''
    <div class="card shadow">
        <div class="card-header bg-primary text-white">
            <h3 class="mb-0"><i class="bi bi-chat-dots"></i> Study Group Chat</h3>
        </div>
        <div class="card-body">
            <div class="chat-box d-flex flex-column" id="chat-box" style="height: 400px;"></div>
            <div class="input-group mt-3">
                <input type="text" id="chat-input" class="form-control form-control-lg" 
                       placeholder="Type your message...">
                <button class="btn btn-primary" type="button" id="chat-send">
                    <i class="bi bi-send"></i>
                </button>
            </div>
        </div>
    </div>
    '''
    custom_js = f'''
    <script>
    document.addEventListener('DOMContentLoaded', () => {{
        const chatBox = document.getElementById('chat-box');
        const chatInput = document.getElementById('chat-input');
        const chatSend = document.getElementById('chat-send');
        const socket = io();
        function addBubble(data) {{
            const bubble = document.createElement('div');
            bubble.className = 'chat-bubble' + (data.username === '{session.get('username')}' ? ' user' : '');
            bubble.innerHTML = `
                <div class="fw-bold">{{
                    data.username === '{session.get('username')}' ? 'You' : data.username
                }}</div>
                <div>${{data.msg}}</div>
                <small class="d-block text-end opacity-75">${{new Date().toLocaleTimeString()}}</small>
            `;
            chatBox.appendChild(bubble);
            chatBox.scrollTop = chatBox.scrollHeight;
        }}
        fetch("{url_for('chat_messages_api')}")
            .then(r => r.json())
            .then(msgs => msgs.forEach(addBubble));
        socket.on('message', addBubble);
        const sendMessage = () => {{
            const msg = chatInput.value.trim();
            if (msg) {{
                socket.send(msg);
                chatInput.value = '';
            }}
        }};
        chatSend.addEventListener('click', sendMessage);
        chatInput.addEventListener('keypress', (e) => {{
            if (e.key === 'Enter') sendMessage();
        }});
    }});
    </script>
    '''
    return render_page(content, custom_js=custom_js)

@app.route('/chat/messages')
def chat_messages_api():
    messages = ChatMessage.query.order_by(ChatMessage.timestamp.asc()).all()
    return jsonify([{"username": m.username, "msg": m.message} for m in messages])

@app.route('/uploads/<user_id>/<filename>')
def uploaded_file(user_id, filename):
    if 'user_id' not in session:
        flash("You don't have permission to access this file.", 'danger')
        return redirect(url_for('home'))
    if not (session['is_admin'] or str(session['user_id']) == user_id):
        flash("You don't have permission to access this file.", 'danger')
        return redirect(url_for('home'))
    return send_from_directory(user_folder(user_id), filename)

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if not session.get('is_admin'):
        flash('Admins only!', 'danger')
        return redirect(url_for('home'))
    users = User.query.all()
    messages = ChatMessage.query.order_by(ChatMessage.timestamp.desc()).all()
    content = '''
    <h2>Admin Panel</h2>
    <div class="admin-section">
        <h4>All Users</h4>
        <ul>
        {% for user in users %}
            <li>
                <b>{{ user.username }}</b> ({{ user.email }})
                {% if not user.is_admin %}
                    <form method="POST" action="{{ url_for('delete_user', user_id=user.id) }}" style="display:inline;">
                        <button class="delete-btn" onclick="return confirm('Delete user?')">Delete User</button>
                    </form>
                {% endif %}
                <br>
                <b>Achievement Image:</b>
                {% set img = None %}
                {% for fname in os.listdir(user_folder(user.id)) %}
                    {% if fname.startswith('achievement.') %}
                        {% set img = fname %}
                    {% endif %}
                {% endfor %}
                {% if img %}
                    <img src="{{ url_for('uploaded_file', user_id=user.id, filename=img) }}" class="img-preview">
                    <form method="POST" action="{{ url_for('delete_user_image', user_id=user.id) }}">
                        <button class="delete-btn" onclick="return confirm('Delete image?')">Delete Image</button>
                    </form>
                {% else %}
                    No image
                {% endif %}
                <br>
                <b>Notes:</b>
                {% set pdfs = [] %}
                {% for fname in os.listdir(user_folder(user.id)) %}
                    {% if fname.endswith('.pdf') %}
                        {% set _ = pdfs.append(fname) %}
                    {% endif %}
                {% endfor %}
                {% if pdfs %}
                    <ul>
                    {% for pdf in pdfs %}
                        <li>
                            <a href="{{ url_for('uploaded_file', user_id=user.id, filename=pdf) }}" target="_blank">{{ pdf }}</a>
                            <form method="POST" action="{{ url_for('delete_user_pdf', user_id=user.id, filename=pdf) }}" style="display:inline;">
                                <button class="delete-btn" onclick="return confirm('Delete PDF?')">Delete</button>
                            </form>
                        </li>
                    {% endfor %}
                    </ul>
                {% else %}
                    No PDFs
                {% endif %}
                <br>
                <b>Personal Docs:</b>
                {% set docs = [] %}
                {% for fname in os.listdir(user_folder(user.id, 'documents')) %}
                    {% set _ = docs.append(fname) %}
                {% endfor %}
                {% if docs %}
                    <ul>
                    {% for doc in docs %}
                        <li>
                            <a href="{{ url_for('serve_document', user_id=user.id, filename=doc) }}" target="_blank">{{ doc }}</a>
                            <form method="POST" action="{{ url_for('admin_delete_document', user_id=user.id, filename=doc) }}" style="display:inline;">
                                <button class="delete-btn" onclick="return confirm('Delete Document?')">Delete</button>
                            </form>
                        </li>
                    {% endfor %}
                    </ul>
                {% else %}
                    No Docs
                {% endif %}
            </li>
        {% endfor %}
        </ul>
    </div>
    <div class="admin-section">
        <h4>All Chat Messages</h4>
        <ul>
        {% for m in messages %}
            <li>
                <b>{{ m.username }}</b>: {{ m.message }}
                <form method="POST" action="{{ url_for('delete_message', msg_id=m.id) }}" style="display:inline;">
                    <button class="delete-btn" onclick="return confirm('Delete message?')">Delete</button>
                </form>
            </li>
        {% endfor %}
        </ul>
    </div>
    '''
    return render_page(content, users=users, os=os, user_folder=user_folder, messages=messages)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if not session.get('is_admin'):
        flash('Admins only!', 'danger')
        return redirect(url_for('home'))
    user = User.query.get(user_id)
    if user:
        folder = user_folder(user_id)
        if os.path.exists(folder):
            shutil.rmtree(folder)
        doc_folder = user_folder(user_id, 'documents')
        if os.path.exists(doc_folder):
            shutil.rmtree(doc_folder)
        db.session.delete(user)
        db.session.commit()
        flash('User deleted.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_user_image/<int:user_id>', methods=['POST'])
def delete_user_image(user_id):
    if not session.get('is_admin'):
        flash('Admins only!', 'danger')
        return redirect(url_for('home'))
    folder = user_folder(user_id)
    for fname in os.listdir(folder):
        if fname.startswith('achievement.'):
            os.remove(os.path.join(folder, fname))
    flash('User achievement image deleted.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_user_pdf/<int:user_id>/<filename>', methods=['POST'])
def delete_user_pdf(user_id, filename):
    if not session.get('is_admin'):
        flash('Admins only!', 'danger')
        return redirect(url_for('home'))
    folder = user_folder(user_id)
    file_path = os.path.join(folder, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        flash('User PDF deleted.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_document/<int:user_id>/<filename>', methods=['POST'])
def admin_delete_document(user_id, filename):
    if not session.get('is_admin'):
        flash('Admins only!', 'danger')
        return redirect(url_for('home'))
    file_path = os.path.join(user_folder(user_id, 'documents'), filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        flash('User document deleted.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_message/<int:msg_id>', methods=['POST'])
def delete_message(msg_id):
    if not session.get('is_admin'):
        flash('Admins only!', 'danger')
        return redirect(url_for('home'))
    msg = ChatMessage.query.get(msg_id)
    if msg:
        db.session.delete(msg)
        db.session.commit()
        flash('Message deleted.', 'success')
    return redirect(url_for('admin_panel'))

@socketio.on('message')
def handle_message(msg):
    username = session.get('username', 'Anonymous')
    chatmsg = ChatMessage(username=username, message=msg)
    db.session.add(chatmsg)
    db.session.commit()
    emit('message', {'username': username, 'msg': msg}, broadcast=True)

@app.before_request
def load_username():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            session['username'] = user.username
            session['is_admin'] = user.is_admin
        else:
            session.clear()
            flash('Session expired. Please login again.', 'warning')
            return redirect(url_for('login'))
    else:
        session['username'] = None
        session['is_admin'] = False

@app.errorhandler(404)
def page_not_found(e):
    return render_page('''
    <div class="text-center py-5">
        <h1 class="display-1 text-primary">404</h1>
        <p class="lead">Oops! The page you're looking for doesn't exist.</p>
        <a href="{{ url_for('home') }}" class="btn btn-primary btn-lg">
            <i class="bi bi-house-door"></i> Return Home
        </a>
    </div>
    '''), 404

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5001) 
     # Changed from default port 5000 to 5001

