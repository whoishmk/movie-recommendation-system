from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from werkzeug.utils import secure_filename
import MySQLdb.cursors


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure key

# Configuration for file uploads
app.config['UPLOAD_FOLDER'] = 'static/uploads/'  # Folder to store uploaded images
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Maximum file size: 16MB

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


# MySQL configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'       # Replace with your MySQL username
app.config['MYSQL_PASSWORD'] = 'admin'   # Replace with your MySQL password
app.config['MYSQL_DB'] = 'movie_recommender'

mysql = MySQL(app)

# Check if file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'loggedin' not in session:
            flash('Please log in to access this page.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes will be added here

@app.route('/')
def index():
    if 'loggedin' in session:
        return redirect(url_for('home'))
    else:
        return render_template('index.html')



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Existing form data processing
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        gender = request.form['gender']

        # Handle profile picture upload
        file = request.files.get('profile_pic')

        # Validate inputs
        if not name or not email or not password or not gender:
            flash('Please fill out all fields.')
            return redirect(url_for('register'))

        # Hash the password
        password_hash = generate_password_hash(password)

        # Check if user exists
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        account = cursor.fetchone()
        if account:
            flash('Account already exists with this email.')
            cursor.close()
            return redirect(url_for('register'))

        # Handle file upload
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # To avoid filename collisions, prepend the user's email or a unique identifier
            filename = f"{email}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
        else:
            # Use default image if no file uploaded or invalid file
            filename = 'default.jpg'

        # Insert new user into database with profile_pic filename
        cursor.execute('''
            INSERT INTO users (name, email, password_hash, gender, profile_pic)
            VALUES (%s, %s, %s, %s, %s)
        ''', (name, email, password_hash, gender, filename))
        mysql.connection.commit()
        cursor.close()
        flash('You have successfully registered! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get form fields
        email = request.form['email']
        password = request.form['password']

        # Fetch user from database using DictCursor
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        account = cursor.fetchone()
        cursor.close()

        if account:
            password_hash = account['password_hash']
            # Verify password
            if check_password_hash(password_hash, password):
                session['loggedin'] = True
                session['id'] = account['id']
                session['name'] = account['name']
                session['profile_pic'] = account['profile_pic']
                flash('Logged in successfully!')
                return redirect(url_for('home'))
            else:
                flash('Incorrect password.')
        else:
            flash('Account not found.')
    return render_template('login.html')




@app.route('/home')
@login_required
def home():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT profile_pic FROM users WHERE id = %s', (session['id'],))
    account = cursor.fetchone()
    cursor.close()
    profile_pic = account['profile_pic'] if account else 'default.jpg'
    return render_template('home.html', profile_pic=profile_pic)


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('login'))



# Run the app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

