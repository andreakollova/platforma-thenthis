from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
from markupsafe import Markup
import re

category_icons = {
    "Python": "fab fa-python",
    "JavaScript": "fab fa-js",
    "HTML": "fab fa-html5",
    "CSS": "fab fa-css3-alt",
    "SQL": "fas fa-database"
}

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
    __tablename__ = 'exercises'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    subcategory = db.Column(db.String(100), nullable=False)
    full_description = db.Column(db.Text, nullable=False)
    code = db.Column(db.Text, nullable=True)
    code_raw = db.Column(db.Text, nullable=True)
    cover_image = db.Column(db.String(150), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    published = db.Column(db.Boolean, default=False)

    @property
    def answers(self):
        if self.code_raw:
            return list(dict.fromkeys(re.findall(r"\{\{\s*(.*?)\s*\}\}", self.code_raw)))
        return []


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ROUTES
@app.route('/')
def home():
    exercises = Exercise.query.filter_by(published=True).order_by(Exercise.id.desc()).limit(6).all()
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
        code_raw = request.form['code']
        code_with_inputs = re.sub(
            r"\{\{\s*(.*?)\s*\}\}",
            r"<input type='text' class='code-input' data-answer='\1' style='width:70px;'>",
            code_raw
        )

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
            code=Markup(code_with_inputs),
            code_raw=code_raw,  # <--- pridaj toto
            cover_image=filename,
            author_id=current_user.id
        )
        db.session.add(new_exercise)
        db.session.commit()

        # Tu použijeme cvicenie.html ale s flagom is_preview=True
        return render_template(
            'cvicenie.html',
            exercise=new_exercise,
            author=current_user,
            is_preview=True,
            solution_clean=re.sub(r"\{\{\s*(.*?)\s*\}\}", r"\1", code_raw or ""),
            category_icon=category_icons.get(category, "fas fa-code")
        )

    return render_template('nove.html')

import re

@app.route('/cvicenie/<int:id>')
def exercise_detail(id):
    exercise = Exercise.query.get_or_404(id)
    author = User.query.get(exercise.author_id)

    # 🔧 Vygeneruj výsledný kód bez {{ ... }}
    final_code = re.sub(r"\{\{\s*(.*?)\s*\}\}", r"\1", exercise.code_raw or "")

    return render_template(
        'cvicenie.html',
        exercise=exercise,
        author=author,
        solution_clean=final_code,  # <--- toto pošleme
        category_icon=category_icons.get(exercise.category, "fas fa-code")
    )


@app.route('/moje-cvicenia')
@login_required
def moje_cvicenia():
    exercises = Exercise.query.filter_by(author_id=current_user.id).order_by(Exercise.id.desc()).all()
    return render_template('moje-cvicenia.html', exercises=exercises)

@app.route('/profil')
def profil():
    return render_template('profil.html')

@app.route('/objavujte')
def objavujte():
    return render_template('objavujte.html')

@app.route('/cvicenie/<int:id>/publish')
@login_required
def publish_exercise(id):
    exercise = Exercise.query.get_or_404(id)

    if exercise.author_id != current_user.id:
        flash("Nemáš oprávnenie publikovať toto cvičenie.")
        return redirect(url_for('dashboard'))

    exercise.published = True
    db.session.commit()

    flash("Cvičenie bolo publikované!")
    return redirect(url_for('moje_cvicenia'))

@app.route('/cvicenie/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_exercise(id):
    exercise = Exercise.query.get_or_404(id)

    # zabezpeč, že len autor môže upravovať
    if exercise.author_id != current_user.id:
        flash("Nemáš oprávnenie upraviť toto cvičenie.")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # aktualizuj hodnoty
        exercise.title = request.form['title']
        exercise.category = request.form['category']
        exercise.subcategory = request.form['subcategory']
        exercise.full_description = request.form['full_description']
        code_raw = request.form['code']
        exercise.code = Markup(re.sub(
            r"\{\{\s*(.*?)\s*\}\}",
            r"<input type='text' class='code-input' data-answer='\1' style='width:70px;'>",
            code_raw
        ))

        file = request.files['cover_image']
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join('static/uploads/covers', filename))
            exercise.cover_image = filename  # prepíš len ak nahráva nový

        db.session.commit()

        flash("Zmeny boli uložené.")
        return render_template('cvicenie.html', exercise=exercise, author=current_user, is_preview=True)

    return render_template('nove.html', exercise=exercise)

@app.route('/cvicenie/delete/<int:id>', methods=['POST'])
@login_required
def delete_exercise(id):
    exercise = Exercise.query.get_or_404(id)
    if exercise.author_id != current_user.id:
        abort(403)
    db.session.delete(exercise)
    db.session.commit()
    flash('Cvičenie bolo vymazané.')
    return redirect(url_for('moje_cvicenia'))


if __name__ == '__main__':
    app.run(debug=True)