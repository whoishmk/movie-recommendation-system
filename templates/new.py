from flask import *
from flask_mysqldb import MySQL

app = Flask(__name__)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'password'
app.config['MYSQL_DB'] = 'movie_recommender'

mysql = MySQL(app)

@app.route('/testing')
def testing():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM carousel")
    carousel = cur.fetchall()
    cur.close()
    return render_template('new_page.html', carousel=carousel)