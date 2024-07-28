from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from functools import wraps
from claudeAgent import dashboard, submit_quiz  # Import the routes
from auth import login_required


app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a random secret key

# Register the routes
app.add_url_rule('/dashboard', 'dashboard', login_required(dashboard), methods=['GET', 'POST'])
app.add_url_rule('/submit_quiz', 'submit_quiz', login_required(submit_quiz), methods=['POST'])



# Database setup
def get_db():
    db = sqlite3.connect('users.db')
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
        db.commit()

init_db()


@app.route('/')
def index():
    if 'user_id' in session:
        # User is logged in, redirect to dashboard
        return redirect(url_for('dashboard'))
    # User is not logged in, show the index page
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None

        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'
        elif db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone() is not None:
            error = f"User {username} is already registered."

        if error is None:
            db.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                       (username, generate_password_hash(password)))
            db.commit()
            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('login'))

        flash(error, 'error')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        if user is None:
            error = 'Incorrect username.'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            flash('Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))

        flash(error, 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('index'))



# @app.route('/dashboard', methods=['GET', 'POST'])
# @login_required
# def dashboard():
#     if request.method == 'POST':
#         video_link = request.form['video_link']
#         print(f"Received video link: {video_link}")
        
#         # Process the video link here
#         # For now, we'll just simulate processing
        
#         # Flash a message to the user
#         flash('Video processed successfully!', 'success')
        
#         # Redirect to a new page (we'll create this next)
#         return redirect(url_for('submit_quiz', video_link=video_link))
    
#     return render_template('dashboard.html')


# @app.route('/submit_quiz')
# @login_required
# def quiz():
#     video_link = request.args.get('video_link')
#     # Here you would generate the quiz based on the video
#     # For now, we'll just pass the link to the template
#     return render_template('quiz.html', video_link=video_link)

if __name__ == '__main__':
    app.run(debug=True)