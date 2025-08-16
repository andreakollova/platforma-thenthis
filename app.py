from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import func
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
from markupsafe import Markup
import re
import random

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

class QuizQuestion(db.Model):
    __tablename__ = 'quiz_questions'
    id = db.Column(db.Integer, primary_key=True)

    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False, index=True)
    subcategory = db.Column(db.String(100), nullable=True, index=True)

    question = db.Column(db.Text, nullable=False)
    A = db.Column(db.Text, nullable=False)
    B = db.Column(db.Text, nullable=False)
    C = db.Column(db.Text, nullable=False)
    D = db.Column(db.Text, nullable=False)
    correct = db.Column(db.String(1), nullable=False)  # 'A' | 'B' | 'C' | 'D'

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    author = db.relationship('User', backref='quiz_questions')

    def to_dict(self):
        return {
            "id": self.id,
            "author_id": self.author_id,
            "category": self.category,
            "subcategory": self.subcategory or "",
            "question": self.question,
            "A": self.A, "B": self.B, "C": self.C, "D": self.D,
            "correct": self.correct,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    @property
    def answers(self):
        if self.code_raw:
            return list(dict.fromkeys(re.findall(r"@@\s*(.*?)\s*@@", self.code_raw)))
        return []


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ROUTES
@app.route('/')
def home():
    # načítame cvičenia spolu s autorom
    exercises = (
        db.session.query(Exercise, User)
        .join(User, Exercise.author_id == User.id)
        .filter(Exercise.published == True)
        .order_by(Exercise.id.desc())
        .limit(9)
        .all()
    )
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
            r"@@\s*(.*?)\s*@@",
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
            solution_clean=re.sub(r"@@\s*(.*?)\s*@@", r"\1", code_raw or ""),
            category_icon=category_icons.get(category, "fas fa-code")
        )

    return render_template('nove.html')

import re

@app.route('/cvicenie/<int:id>')
def exercise_detail(id):
    exercise = Exercise.query.get_or_404(id)
    author = User.query.get(exercise.author_id)

    # 🔧 Vygeneruj výsledný kód bez {{ ... }}
    final_code = re.sub(r"@@\s*(.*?)\s*@@", r"\1", exercise.code_raw or "")

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
    category = request.args.get('category')
    subcategory = request.args.get('subcategory')

    query = Exercise.query.filter_by(author_id=current_user.id)

    if category:
        query = query.filter_by(category=category)
    if subcategory:
        query = query.filter_by(subcategory=subcategory)

    exercises = query.order_by(Exercise.id.desc()).all()
    return render_template(
        'moje-cvicenia.html',
        exercises=exercises,
        selected_category=category,
        selected_subcategory=subcategory
    )

@app.route('/profil')
def profil():
    return render_template('profil.html')

@app.route("/objavujte", methods=["GET"])
def objavujte():
    category = request.args.get('category')
    subcategory = request.args.get('subcategory')

    # Query všetky cvičenia s autormi
    query = db.session.query(Exercise, User).join(User, Exercise.author_id == User.id)

    # Filter podľa kategórie (ak je vyplnená)
    if category:
        query = query.filter(Exercise.category == category)

    # Filter podľa podkategórie (ak je vyplnená)
    if subcategory:
        query = query.filter(Exercise.subcategory == subcategory)

    # Výsledné cvičenia
    exercises = query.all()

    # Náhodné cvičenie z filtrovanej množiny (napr. len JS)
    random_query = db.session.query(Exercise, User).join(User).filter(Exercise.published == True)

    if category:
        random_query = random_query.filter(Exercise.category == category)
    if subcategory:
        random_query = random_query.filter(Exercise.subcategory == subcategory)

    filtered_exercises = random_query.all()
    random_exercise = random.choice(filtered_exercises) if filtered_exercises else None

    return render_template(
        "objavujte.html",
        exercises=exercises,
        random_exercise=random_exercise
    )

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
            r"@@\s*(.*?)\s*@@",
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

@app.route('/projekty')
def projekty():
    return render_template('projekty.html')

@app.route('/random')
def random_page():
    return render_template('random.html')

@app.route('/o-platforme')
def o_platforme():
    return render_template('platforma.html')

@app.route('/kviz')
@login_required
def kviz():
    return render_template('kviz.html', user=current_user)

@app.route('/kviz-spustit')
@login_required
def kviz_spustit():
    return render_template('kviz-spustit.html', user=current_user)

def _apply_scope(query, scope):
    # "mine" = len tvoje otázky (default), "all" = všetkých
    if scope == 'all':
        return query
    return query.filter(QuizQuestion.author_id == (current_user.id if current_user.is_authenticated else -1))

def _validate_question_payload(data, is_update=False):
    required = ['category','subcategory','question','A','B','C','D','correct']
    if not is_update:
        for k in required:
            if not data.get(k):
                return f"Missing field: {k}"
    if data.get('correct') and data['correct'] not in ['A','B','C','D']:
        return "Field 'correct' must be one of A,B,C,D"
    return None

@app.route('/api/questions', methods=['GET', 'POST'])
@login_required
def api_questions():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        err = _validate_question_payload(data)
        if err: return jsonify({"error": err}), 400

        q = QuizQuestion(
            author_id=current_user.id,
            category=data['category'],
            subcategory=data.get('subcategory') or "",
            question=data['question'].strip(),
            A=data['A'].strip(), B=data['B'].strip(), C=data['C'].strip(), D=data['D'].strip(),
            correct=data['correct']
        )
        db.session.add(q)
        db.session.commit()
        return jsonify({"item": q.to_dict()}), 201

    # GET
    scope = request.args.get('scope', 'mine')         # mine|all
    category = request.args.get('category')
    subcategory = request.args.get('subcategory')
    search = request.args.get('search')
    page = request.args.get('page', type=int)
    page_size = request.args.get('page_size', type=int, default=10)
    limit = request.args.get('limit', type=int)       # alternatíva k stránkovaniu
    random_flag = request.args.get('random', default='0') in ['1','true','True']

    q = _apply_scope(QuizQuestion.query, scope)

    if category and category != '__all__':
        q = q.filter(QuizQuestion.category == category)
    if subcategory and subcategory != '__all__':
        q = q.filter(QuizQuestion.subcategory == subcategory)
    if search:
        like = f"%{search}%"
        q = q.filter(QuizQuestion.question.ilike(like))

    if random_flag:
        q = q.order_by(func.random())

    # 3 režimy: stránkovanie | limit | všetko (capneme na 1000)
    if page:
        page = max(1, page)
        page_size = max(1, min(50, page_size))
        total = q.count()
        items = q.order_by(QuizQuestion.id.desc()).offset((page-1)*page_size).limit(page_size).all()
        return jsonify({
            "items": [it.to_dict() for it in items],
            "total": total,
            "page": page,
            "page_size": page_size
        })
    elif limit:
        limit = max(1, min(200, limit))
        items = q.limit(limit).all()
        return jsonify({"items": [it.to_dict() for it in items], "total": len(items)})
    else:
        items = q.order_by(QuizQuestion.id.desc()).limit(1000).all()
        return jsonify({"items": [it.to_dict() for it in items], "total": len(items)})

@app.route('/api/questions/<int:q_id>', methods=['GET','PUT','DELETE'])
@login_required
def api_question_detail(q_id):
    q = QuizQuestion.query.get_or_404(q_id)

    # len autor môže upravovať/mazať
    if request.method in ['PUT','DELETE'] and q.author_id != current_user.id:
        return jsonify({"error":"Nemáš oprávnenie upravovať alebo mazať túto otázku."}), 403

    if request.method == 'GET':
        # čítať môže autor; ak by si chcela public, prispôsob
        if q.author_id != current_user.id:
            return jsonify({"error":"Nedostupné."}), 403
        return jsonify({"item": q.to_dict()})

    if request.method == 'PUT':
        data = request.get_json(silent=True) or {}
        err = _validate_question_payload(data, is_update=True)
        if err: return jsonify({"error": err}), 400

        q.category = data.get('category', q.category)
        q.subcategory = data.get('subcategory', q.subcategory)
        q.question = data.get('question', q.question)
        q.A = data.get('A', q.A)
        q.B = data.get('B', q.B)
        q.C = data.get('C', q.C)
        q.D = data.get('D', q.D)
        if data.get('correct') in ['A','B','C','D']:
            q.correct = data['correct']
        db.session.commit()
        return jsonify({"item": q.to_dict()})

    # DELETE
    db.session.delete(q)
    db.session.commit()
    return jsonify({"status":"deleted","id":q_id})

@app.route('/api/subcategories')
@login_required
def api_subcategories():
    scope = request.args.get('scope','mine')
    category = request.args.get('category')
    q = _apply_scope(QuizQuestion.query, scope)
    if category and category != '__all__':
        q = q.filter(QuizQuestion.category == category)
    subs = q.with_entities(QuizQuestion.subcategory).distinct().all()
    return jsonify({"subcategories":[s[0] for s in subs if s[0]]})

if __name__ == '__main__':
    app.run(debug=True)