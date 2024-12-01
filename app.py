from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from werkzeug.utils import secure_filename
import MySQLdb.cursors
from datetime import datetime

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

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'loggedin' not in session:
            flash('Please log in to access this page.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def add_notification(user_id, message, url):
    cursor = mysql.connection.cursor()
    cursor.execute("""
        INSERT INTO notifications (user_id, message, url)
        VALUES (%s, %s, %s)
    """, (user_id, message, url))
    mysql.connection.commit()
    cursor.close()


@app.context_processor
def inject_notifications():
    if 'loggedin' in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("""
            SELECT * FROM notifications WHERE user_id = %s AND is_read = FALSE ORDER BY created_at DESC
        """, (session['id'],))
        notifications = cursor.fetchall()
        cursor.close()
        return dict(notifications=notifications)
    return dict(notifications=[])

@app.route('/notifications')
@login_required
def view_notifications():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC
    """, (session['id'],))
    all_notifications = cursor.fetchall()
    cursor.close()
    return render_template('notifications.html', notifications=all_notifications)

@app.route('/mark_notification_as_read/<int:notification_id>')
@login_required
def mark_notification_as_read(notification_id):
    cursor = mysql.connection.cursor()
    cursor.execute("""
        UPDATE notifications SET is_read = TRUE WHERE id = %s AND user_id = %s
    """, (notification_id, session['id']))
    mysql.connection.commit()
    cursor.close()
    return redirect(request.referrer or url_for('view_notifications'))

# Routes will be added here

@app.route('/')
def index():
    if 'loggedin' in session:
        return redirect(url_for('home'))
    else:
        return render_template('home.html')



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
    return redirect(url_for('index'))


@app.route('/discussions')
def discussions():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("""
        SELECT threads.*, users.name
        FROM threads
        JOIN users ON threads.user_id = users.id
        ORDER BY threads.created_at DESC
    """)
    threads = cursor.fetchall()
    cursor.close()
    return render_template('discussions.html', threads=threads)

@app.route('/thread/<int:thread_id>')
def view_thread(thread_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    # Fetch thread details
    cursor.execute("""
        SELECT threads.*, users.name
        FROM threads
        JOIN users ON threads.user_id = users.id
        WHERE threads.id = %s
    """, (thread_id,))
    thread = cursor.fetchone()
    if not thread:
        flash('Thread not found.')
        return redirect(url_for('discussions'))
    # Fetch messages in the thread
    cursor.execute("""
        SELECT messages.*, users.name
        FROM messages
        JOIN users ON messages.user_id = users.id
        WHERE messages.thread_id = %s
        ORDER BY messages.created_at ASC
    """, (thread_id,))
    messages = cursor.fetchall()
    cursor.close()
    return render_template('view_thread.html', thread=thread, messages=messages)

@app.route('/create_thread', methods=['GET', 'POST'])
@login_required
def create_thread():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        user_id = session['id']

        # Handle image upload
        file = request.files.get('image')
        image_filename = None
        if file and allowed_file(file.filename):
            image_filename = secure_filename(file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            file.save(image_path)

        # Insert thread into the database
        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO threads (title, content, user_id, image)
            VALUES (%s, %s, %s, %s)
        """, (title, content, user_id, image_filename))
        mysql.connection.commit()
        cursor.close()

        flash('Thread created successfully.')
        return redirect(url_for('discussions'))

    return render_template('create_thread.html')



@app.route('/edit_message/<int:message_id>', methods=['GET', 'POST'])
@login_required
def edit_message(message_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    # Fetch the message
    cursor.execute("SELECT * FROM messages WHERE id = %s", (message_id,))
    message = cursor.fetchone()
    if not message:
        flash('Message not found.')
        return redirect(url_for('discussions'))
    if message['user_id'] != session['id']:
        flash('You are not authorized to edit this message.')
        return redirect(url_for('view_thread', thread_id=message['thread_id']))
    if request.method == 'POST':
        content = request.form['content']
        cursor.execute("""
            UPDATE messages SET content = %s, updated_at = %s WHERE id = %s
        """, (content, datetime.now(), message_id))
        mysql.connection.commit()
        cursor.close()
        flash('Message updated successfully.')
        return redirect(url_for('view_thread', thread_id=message['thread_id']))
    cursor.close()
    return render_template('edit_message.html', message=message)


@app.route('/delete_message/<int:message_id>', methods=['POST'])
@login_required
def delete_message(message_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    # Fetch the message
    cursor.execute("SELECT * FROM messages WHERE id = %s", (message_id,))
    message = cursor.fetchone()
    if not message:
        flash('Message not found.')
        return redirect(url_for('discussions'))
    if message['user_id'] != session['id']:
        flash('You are not authorized to delete this message.')
        return redirect(url_for('view_thread', thread_id=message['thread_id']))
    cursor.execute("DELETE FROM messages WHERE id = %s", (message_id,))
    mysql.connection.commit()
    cursor.close()
    flash('Message deleted successfully.')
    return redirect(url_for('view_thread', thread_id=message['thread_id']))




@app.route('/edit_thread/<int:thread_id>', methods=['GET', 'POST'])
@login_required
def edit_thread(thread_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    # Fetch the thread
    cursor.execute("SELECT * FROM threads WHERE id = %s", (thread_id,))
    thread = cursor.fetchone()
    if not thread:
        flash('Thread not found.')
        return redirect(url_for('discussions'))
    if thread['user_id'] != session['id']:
        flash('You are not authorized to edit this thread.')
        return redirect(url_for('view_thread', thread_id=thread_id))
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        cursor.execute("""
            UPDATE threads SET title = %s, content = %s, updated_at = %s WHERE id = %s
        """, (title, content, datetime.now(), thread_id))
        mysql.connection.commit()
        cursor.close()
        flash('Thread updated successfully.')
        return redirect(url_for('view_thread', thread_id=thread_id))
    cursor.close()
    return render_template('edit_thread.html', thread=thread)


@app.route('/delete_thread/<int:thread_id>', methods=['POST'])
@login_required
def delete_thread(thread_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    # Fetch the thread
    cursor.execute("SELECT * FROM threads WHERE id = %s", (thread_id,))
    thread = cursor.fetchone()
    if not thread:
        flash('Thread not found.')
        return redirect(url_for('discussions'))
    if thread['user_id'] != session['id']:
        flash('You are not authorized to delete this thread.')
        return redirect(url_for('view_thread', thread_id=thread_id))
    cursor.execute("DELETE FROM threads WHERE id = %s", (thread_id,))
    mysql.connection.commit()
    cursor.close()
    flash('Thread deleted successfully.')
    return redirect(url_for('discussions'))


@app.route('/post_message/<int:thread_id>', methods=['POST'])
@login_required
def post_message(thread_id):
    content = request.form['content']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    # Insert the message
    cursor.execute("""
        INSERT INTO messages (thread_id, user_id, content, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s)
    """, (thread_id, session['id'], content, datetime.now(), datetime.now()))
    mysql.connection.commit()

    # Fetch the thread creator
    cursor.execute("""
        SELECT user_id FROM threads WHERE id = %s
    """, (thread_id,))
    thread = cursor.fetchone()

    # Add notification for the thread creator if they are not the one posting
    if thread and thread['user_id'] != session['id']:
        message = f"{session['name']} replied to your thread."
        url = url_for('view_thread', thread_id=thread_id)
        add_notification(thread['user_id'], message, url)

    cursor.close()
    return redirect(url_for('view_thread', thread_id=thread_id))





















# Run the app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

