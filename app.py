from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename

# Flask setup
app = Flask(__name__)
app.secret_key = 'tajny-kluc'

# DB setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://uwbztwus25ch8p4qqlqu:cHfJeYn25o85BqBssgalamtqUcXQgW@byqxitncl5zqn2hqgdb4-postgresql.services.clever-cloud.com:50013/byqxitncl5zqn2hqgdb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads/profiles'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# USER model
class User(db.Model, UserMixin):
    __tablename__ = 'users'  # <-- toto pridaj
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    photo = db.Column(db.String(256), default="default.jpg")

class Exercise(db.Model):
    __tablename__ = 'exercises'  # <- DÔLEŽITÉ
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    subcategory = db.Column(db.String(100), nullable=False)
    full_description = db.Column(db.Text, nullable=False)
    code = db.Column(db.Text, nullable=True)
    cover_image = db.Column(db.String(150), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ROUTES
@app.route('/')
def home():
    exercises = Exercise.query.order_by(Exercise.id.desc()).limit(6).all()
    return render_template('index.html', exercises=exercises)

# REGISTRATION ROUTE
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        photo = request.files['photo']

        if User.query.filter_by(email=email).first():
            flash('Účet s týmto emailom už existuje.')
            return redirect(url_for('register'))

        filename = "default.jpg"
        if photo and photo.filename:
            filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_user = User(name=name, email=email, password=password, photo=filename)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        flash('Vitaj! Účet bol úspešne vytvorený.')
        return redirect(url_for('dashboard'))

    return render_template('register.html')

# LOGIN ROUTE
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', show_modal=True)
    return render_template('login.html')

# LOGOUT
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Bola si odhlásená.')
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/cvicenia')
def cvicenia():
    return render_template('cvicenia.html')

@app.route('/cvicenie/nove', methods=['GET', 'POST'])
@login_required
def nove_cvicenie():
    if request.method == 'POST':
        title = request.form['title']
        category = request.form['category']
        subcategory = request.form['subcategory']
        full_description = request.form['full_description']
        code = request.form['code']

        file = request.files['cover_image']
        filename = "default.png"
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join('static/uploads/covers', filename))

        new_exercise = Exercise(
            title=title,
            category=category,
            subcategory=subcategory,
            full_description=full_description,
            code=code,
            cover_image=filename,
            author_id=current_user.id
        )
        db.session.add(new_exercise)
        db.session.commit()
        flash('Cvičenie bolo úspešne vytvorené!')

        return redirect(url_for('exercise_detail', id=new_exercise.id))

    return render_template('nove.html')

@app.route('/cvicenie/<int:id>')
def exercise_detail(id):
    exercise = Exercise.query.get_or_404(id)
    author = User.query.get(exercise.author_id)
    return render_template('cvicenie.html', exercise=exercise, author=author)

@app.route('/moje-cvicenia')
def moje_cvicenia():
    return render_template('moje-cvicenia.html')

@app.route('/profil')
def profil():
    return render_template('profil.html')

@app.route('/objavujte')
def objavujte():
    return render_template('objavujte.html')


if __name__ == '__main__':
    app.run(debug=True)