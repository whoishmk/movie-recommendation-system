from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from werkzeug.utils import secure_filename
import MySQLdb.cursors
import random
from datetime import datetime
import pickle
import pandas as pd
import numpy as np
import requests
from sentence_transformers import SentenceTransformer
import torch
from sklearn.neighbors import NearestNeighbors

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure key

# Configuration for file uploads
app.config['UPLOAD_FOLDER'] = 'static/uploads/'  # Folder to store uploaded images
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Maximum file size: 16MB

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# MySQL configuration for flask_mysqldb
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'       # Replace with your MySQL username
app.config['MYSQL_PASSWORD'] = 'admin'   # Replace with your MySQL password
app.config['MYSQL_DB'] = 'movie_recommender'

mysql = MySQL(app)

# TMDb API Key for fetching posters
TMDB_API_KEY = "829ab52a87e9772ae8219c46c35ba8ca"

# Load precomputed data for movie recommendations
with open("precomputed_data.pkl", "rb") as f:
    data = pickle.load(f)

title_embeddings = data['title_embeddings']
cosine_sim = data['cosine_sim']
movie_titles = data['movie_titles']
X = data['X']
user_mapper = data['user_mapper']
movie_mapper = data['movie_mapper']
user_inv_mapper = data['user_inv_mapper']
movie_inv_mapper = data['movie_inv_mapper']

# Database configuration for mysql.connector (used by script 2 logic)
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'admin',
    'database': 'movie_recommender'
}

def load_data_from_db(table_name):
    with app.app_context():
        cursor = mysql.connection.cursor()
        query = f"SELECT * FROM {table_name}"
        cursor.execute(query)
        data = cursor.fetchall()  # Fetch all rows as a list of tuples
        column_names = [desc[0] for desc in cursor.description]  # Get column names
        cursor.close()
        # Convert to a list of dictionaries for easier manipulation
        df = pd.DataFrame(data, columns=column_names)
        return df

# Load data from database using mysql.connector
links = load_data_from_db("links")
movies = load_data_from_db("movies")

# Helper Functions for Recommendation
def find_similar_movies(movie_id, k=10, metric='cosine'):
    movie_ind = movie_mapper[movie_id]
    movie_vec = X.T[movie_ind]
    kNN = NearestNeighbors(n_neighbors=k+1, metric=metric)
    kNN.fit(X.T)
    neighbors = kNN.kneighbors(movie_vec, return_distance=False).flatten()
    return [movie_inv_mapper[n] for n in neighbors if n != movie_ind]

def movie_finder(title):
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    title_embeddings_on_device = torch.tensor(title_embeddings, device=device)
    model = SentenceTransformer('all-MiniLM-L6-v2', device=device)
    input_embedding = model.encode(title, convert_to_tensor=True).to(device)
    scores = torch.matmul(title_embeddings_on_device, input_embedding)
    best_match_idx = scores.argmax().item()
    return movie_titles[best_match_idx]

poster_cache = {}
def get_movie_posters(tmdb_ids):
    poster_urls = []
    for tmdb_id in tmdb_ids:
        if tmdb_id in poster_cache:
            poster_urls.append(poster_cache[tmdb_id])
        else:
            url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}"
            try:
                response = requests.get(url, timeout=5).json()
                if "poster_path" in response and response["poster_path"]:
                    poster_url = f"https://image.tmdb.org/t/p/w500{response['poster_path']}"
                else:
                    poster_url = "static/no_image_available.png"
            except Exception as e:
                print(f"Error fetching poster for TMDb ID {tmdb_id}: {e}")
                poster_url = "static/no_image_available.png"
            poster_cache[tmdb_id] = poster_url
            poster_urls.append(poster_url)
    return poster_urls

def get_random_movie():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM movies ORDER BY RAND() LIMIT 1")
    movie = cursor.fetchone()
    cursor.close()
    return movie

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

@app.route('/')
def index():
    if 'loggedin' in session:
        return redirect(url_for('home'))
    else:
        return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        gender = request.form.get('gender')
        biography = request.form.get('biography', '')
        hobbies = request.form.get('hobbies', '')
        movie_interests = request.form.get('movie_interests', '')
        file = request.files.get('profile_pic')

        # Validation check
        if not name or not email or not password or not gender:
            flash('Please fill out all required fields.')
            return redirect(url_for('register'))

        # Hash the password
        password_hash = generate_password_hash(password)

        # Check if account already exists
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        account = cursor.fetchone() 
        if account:
            flash('Account already exists with this email.')
            cursor.close()
            return redirect(url_for('register'))

        # Save profile picture
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filename = f"{email}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
        else:
            filename = 'default.jpg'

        # Insert into database including new fields
        cursor.execute('''
            INSERT INTO users (name, email, password_hash, gender, profile_pic, biography, hobbies, movie_interests)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (name, email, password_hash, gender, filename, biography, hobbies, movie_interests))
        mysql.connection.commit()
        cursor.close()

        flash('You have successfully registered! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        account = cursor.fetchone()
        cursor.close()

        if account:
            password_hash = account['password_hash']
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
 
@app.route('/home', methods=['GET', 'POST'])
@login_required
def home():
    # Fetch user's profile pic
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT profile_pic FROM users WHERE id = %s', (session['id'],))
    account = cursor.fetchone()
    cursor.close()
    profile_pic = account['profile_pic'] if account else 'default.jpg'

    # Handle user input from the form
    if request.method == 'POST':
        user_input = request.form.get('movie', '').strip()
        if not user_input:
            user_input = "Toy Story (1995)"
    else:
        user_input = "Toy Story (1995)"  # Default movie

    # Integrate recommendation logic
    try:
        # Find the movie name best matching the user input
        movie_name = movie_finder(user_input)
        
        # Match the movie_name to get movie_id from the movies DataFrame
        movie_id = next((movies['movieId'][i] for i, title in enumerate(movies['title']) if title == movie_name), None)

        # Collaborative Filtering recommendations
        similar_movies = find_similar_movies(movie_id, k=10)
        cf_tmdb_ids = links[links['movieId'].isin(similar_movies)]['tmdbId'].tolist()
        cf_posters = get_movie_posters(cf_tmdb_ids)

        # Content-Based Filtering recommendations
        movie_index = movies[movies['movieId'] == movie_id].index[0]
        content_similarities = list(enumerate(cosine_sim[movie_index]))
        content_similarities = sorted(content_similarities, key=lambda x: x[1], reverse=True)[1:11]
        cb_movie_ids = [movies.iloc[i[0]]['movieId'] for i in content_similarities]
        cb_tmdb_ids = links[links['movieId'].isin(cb_movie_ids)]['tmdbId'].tolist()
        cb_posters = get_movie_posters(cb_tmdb_ids)

    except Exception as e:
        movie_name = user_input
        cf_posters = []
        cb_posters = []
        flash(f"No recommendations found for '{user_input}'. Error: {e}", "danger")

    # Fetch carousel images
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT image_path FROM carousel')
    carousel_images = [row['image_path'] for row in cursor.fetchall()]
    cursor.close()

    return render_template('home.html',
                           profile_pic=profile_pic,
                           movie_name=movie_name,
                           cf_posters=cf_posters,
                           cb_posters=cb_posters,
                           carousel_images=carousel_images)


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

        file = request.files.get('image')
        image_filename = None
        if file and allowed_file(file.filename):
            image_filename = secure_filename(file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            file.save(image_path)

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
    cursor.execute("""
        INSERT INTO messages (thread_id, user_id, content, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s)
    """, (thread_id, session['id'], content, datetime.now(), datetime.now()))
    mysql.connection.commit()

    cursor.execute("""
        SELECT user_id FROM threads WHERE id = %s
    """, (thread_id,))
    thread = cursor.fetchone()

    if thread and thread['user_id'] != session['id']:
        message = f"{session['name']} replied to your thread."
        url = url_for('view_thread', thread_id=thread_id)
        add_notification(thread['user_id'], message, url)

    cursor.close()
    return redirect(url_for('view_thread', thread_id=thread_id))

@app.route('/profile')
@login_required
def profile():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM users WHERE id = %s', (session['id'],))
    user = cursor.fetchone()
    cursor.execute('SELECT * FROM threads WHERE user_id = %s ORDER BY created_at DESC', (session['id'],))
    discussions = cursor.fetchall()
    cursor.close()
    return render_template('profile.html', user=user, discussions=discussions)

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        name = request.form['name']
        gender = request.form['gender']
        profile_pic = request.files.get('profile_pic')

        if profile_pic and allowed_file(profile_pic.filename):
            filename = secure_filename(profile_pic.filename)
            profile_pic_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            profile_pic.save(profile_pic_path)
        else:
            filename = session['profile_pic']

        cursor = mysql.connection.cursor()
        cursor.execute("""
            UPDATE users SET name = %s, gender = %s, profile_pic = %s WHERE id = %s
        """, (name, gender, filename, session['id']))
        mysql.connection.commit()
        cursor.close()

        session['name'] = name
        session['profile_pic'] = filename

        flash('Profile updated successfully.')
        return redirect(url_for('profile'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM users WHERE id = %s', (session['id'],))
    user = cursor.fetchone()
    cursor.close()
    return render_template('edit_profile.html', user=user)

@app.route('/user/<int:user_id>')
def user_profile(user_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()

    if not user:
        flash('User not found.')
        return redirect(url_for('discussions'))

    cursor.execute('SELECT * FROM threads WHERE user_id = %s ORDER BY created_at DESC', (user_id,))
    discussions = cursor.fetchall()
    cursor.close()

    return render_template('user_profile.html', user=user, discussions=discussions)

@app.route('/insights/<int:user_id>')
def insights(user_id):
    user_insights = {"activity": "Very Active", "threads_created": 10}  # Example data
    return render_template('insights.html', insights=user_insights)

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '').strip()
    if not query:
        flash("Please enter a search query!", "warning")
        return redirect(url_for('home'))

    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT * FROM movies
        WHERE movie_title LIKE %s OR 
              movie_description LIKE %s
    """, (f"%{query}%", f"%{query}%"))
    results = cursor.fetchall()
    cursor.close()

    return render_template('search_results.html', query=query, results=results)

# If you want, you can remove the chatbot logic or keep it:
# For brevity, we won't remove it now.









































if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
