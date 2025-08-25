from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.pool import NullPool
from sqlalchemy import func, text
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from markupsafe import Markup
import os, re, random, json

# --------------------------------------------------------------------------- #
# Upload helpers
# --------------------------------------------------------------------------- #

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg"}

def _save_project_image(file_storage, kind="cover"):
    if not file_storage or not file_storage.filename:
        raise ValueError("Chýba súbor.")
    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Nepodporovaný formát obrázka.")
    subdir = "project-icons" if kind == "icon" else "projects"
    os.makedirs(os.path.join("static", subdir), exist_ok=True)
    safe_name = secure_filename(file_storage.filename)
    fname = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{safe_name}"
    fpath = os.path.join("static", subdir, fname)
    file_storage.save(fpath)
    # relatívne k /static
    return os.path.join(subdir, fname)

# --------------------------------------------------------------------------- #
# App / DB config
# --------------------------------------------------------------------------- #

app = Flask(__name__)
app.secret_key = 'tajny-kluc'

# Clever-Cloud Postgres
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'postgresql://uwbztwus25ch8p4qqlqu:'
    'cHfJeYn25o85BqBssgalamtqUcXQgW@'
    'byqxitncl5zqn2hqgdb4-postgresql.services.clever-cloud.com:50013/'
    'byqxitncl5zqn2hqgdb4'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_size": 2,
    "max_overflow": 0,
    "pool_timeout": 30,
    # ak by bolo treba, vieš prepnúť na NullPool:
    # "poolclass": NullPool,
}

# uploads
app.config['UPLOAD_FOLDER'] = 'static/uploads/profiles'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/uploads/covers', exist_ok=True)   # covers pre cvičenia
os.makedirs('static/project-icons', exist_ok=True)    # ikonky projektov
os.makedirs('static/projects', exist_ok=True)         # cover obrázky projektov

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

category_icons = {
    "Python": "fab fa-python",
    "JavaScript": "fab fa-js",
    "HTML": "fab fa-html5",
    "CSS": "fab fa-css3-alt",
    "SQL": "fas fa-database"
}

# --------------------------------------------------------------------------- #
# MODELS
# --------------------------------------------------------------------------- #

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(150), nullable=False)
    email    = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    photo    = db.Column(db.String(256), default="default.jpg")


class Exercise(db.Model):
    __tablename__ = 'exercises'
    id               = db.Column(db.Integer, primary_key=True)
    title            = db.Column(db.String(150), nullable=False)
    category         = db.Column(db.String(50), nullable=False)
    subcategory      = db.Column(db.String(100), nullable=False)
    full_description = db.Column(db.Text, nullable=False)
    code             = db.Column(db.Text, nullable=True)   # s <input>
    code_raw         = db.Column(db.Text, nullable=True)   # s @@odpoveď@@
    cover_image      = db.Column(db.String(150), nullable=True)
    author_id        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    published        = db.Column(db.Boolean, default=False)

    @property
    def answers(self):
        if self.code_raw:
            return list(dict.fromkeys(re.findall(r"@@\s*(.*?)\s*@@", self.code_raw)))
        return []


class Project(db.Model):
    __tablename__ = 'projects'
    id            = db.Column(db.Integer, primary_key=True)
    author_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title         = db.Column(db.String(200), nullable=False)
    level         = db.Column(db.String(50))
    category      = db.Column(db.String(80))
    time_estimate = db.Column(db.String(80))
    preview_url   = db.Column(db.String(300))
    langs         = db.Column(db.String(200))      # CSV: "Python,JavaScript"
    icon_path     = db.Column(db.String(300))      # relatívne k /static
    cover_path    = db.Column(db.String(300))      # relatívne k /static
    steps_count   = db.Column(db.Integer, default=0)
    assignment    = db.Column(db.Text)
    tips          = db.Column(db.Text)
    published     = db.Column(db.Boolean, default=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    steps = db.relationship(
        'ProjectStep',
        backref='project',
        cascade='all, delete-orphan',
        order_by='ProjectStep.order'
    )

    @property
    def langs_list(self):
        if not self.langs:
            return []
        return [x.strip() for x in self.langs.split(',') if x.strip()]


class ProjectStep(db.Model):
    __tablename__ = 'project_steps'
    id         = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    order      = db.Column(db.Integer, default=0)
    title      = db.Column(db.String(200))
    explain    = db.Column(db.Text)
    bullets    = db.Column(db.Text)    # newline separated
    checks     = db.Column(db.Text)
    hint       = db.Column(db.Text)
    file_name  = db.Column(db.String(120))
    code       = db.Column(db.Text)
    added_csv  = db.Column(db.Text)    # "0,3,4"

# --------------------------------------------------------------------------- #
# DB bootstrap / light migrations
# --------------------------------------------------------------------------- #

with app.app_context():
    db.create_all()
    # ad-hoc doplnenie stĺpcov (bez pádu, ak už sú)
    stmts = [
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS assignment TEXT",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS tips TEXT",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS icon_path VARCHAR(300)",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS cover_path VARCHAR(300)",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS steps_count INTEGER DEFAULT 0",
        "ALTER TABLE project_steps ADD COLUMN IF NOT EXISTS added_csv TEXT"
    ]
    for s in stmts:
        db.session.execute(text(s))
    db.session.commit()

# --------------------------------------------------------------------------- #
# HELPERS (projekty)
# --------------------------------------------------------------------------- #

def _flags_from_csv(csv_value):
    """'Python, JavaScript' -> {'Python': True, 'JavaScript': True}"""
    if not csv_value:
        return {}
    parts = [p.strip() for p in str(csv_value).split(',') if p.strip()]
    return {p: True for p in parts}

def _list_from_any(v):
    """bezpečne pretypuj na list (list | JSON | CSV | riadky)"""
    if v is None or v == '':
        return []
    if isinstance(v, list):
        return v
    s = str(v).strip()
    try:
        j = json.loads(s)
        if isinstance(j, list):
            return j
    except Exception:
        pass
    if '\n' in s:
        return [x.strip() for x in s.split('\n') if x.strip()]
    return [x.strip() for x in s.split(',') if x.strip()]

def _ints_from_csv(s):
    out = []
    if not s:
        return out
    for p in str(s).split(','):
        p = p.strip()
        if p.isdigit():
            out.append(int(p))
    return out

# --------------------------------------------------------------------------- #
# LOGIN
# --------------------------------------------------------------------------- #

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --------------------------------------------------------------------------- #
# PUBLIC / AUTH ROUTES
# --------------------------------------------------------------------------- #

@app.route('/')
def home():
    exercises = (
        db.session.query(Exercise, User)
        .join(User, Exercise.author_id == User.id)
        .filter(Exercise.published == True)
        .order_by(Exercise.id.desc())
        .limit(9)
        .all()
    )

    # ➜ PRIDANÉ: projekty pre carousel na indexe
    projects = (
        Project.query
        .filter_by(published=True)
        .order_by(Project.id.desc())
        .limit(12)
        .all()
    )

    return render_template('index.html', exercises=exercises, projects=projects)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name  = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        photo = request.files.get('photo')

        if User.query.filter_by(email=email).first():
            flash('Účet s týmto emailom už existuje.')
            return redirect(url_for('register'))

        filename = "default.jpg"
        if photo and photo.filename:
            filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        u = User(name=name, email=email, password=password, photo=filename)
        db.session.add(u)
        db.session.commit()
        login_user(u)
        flash('Vitaj! Účet bol vytvorený.')
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']
        u = User.query.filter_by(email=email).first()
        if u and check_password_hash(u.password, password):
            login_user(u)
            return redirect(url_for('dashboard'))
        return render_template('login.html', show_modal=True)
    return render_template('login.html')

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

# --------------------------------------------------------------------------- #
# CVIČENIA
# --------------------------------------------------------------------------- #

@app.route('/cvicenia')
def cvicenia():
    return render_template('cvicenia.html')

@app.route('/cvicenie/nove', methods=['GET','POST'])
@login_required
def nove_cvicenie():
    if request.method == 'POST':
        title   = request.form['title']
        category= request.form['category']
        subcat  = request.form['subcategory']
        desc    = request.form['full_description']
        code_raw= request.form['code']

        code_with_inputs = re.sub(
            r"@@\s*(.*?)\s*@@",
            r"<input type='text' class='code-input' data-answer='\1' style='width:70px;'>",
            code_raw or ''
        )

        file = request.files.get('cover_image')
        filename = "default.png"
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join('static/uploads/covers', filename))

        ex = Exercise(
            title=title, category=category, subcategory=subcat,
            full_description=desc, code=Markup(code_with_inputs),
            code_raw=code_raw, cover_image=filename, author_id=current_user.id
        )
        db.session.add(ex); db.session.commit()

        return render_template(
            'cvicenie.html',
            exercise=ex, author=current_user, is_preview=True,
            solution_clean=re.sub(r"@@\s*(.*?)\s*@@", r"\1", code_raw or ""),
            category_icon=category_icons.get(category, "fas fa-code")
        )
    return render_template('nove.html')

@app.route('/cvicenie/<int:id>')
def exercise_detail(id):
    ex = Exercise.query.get_or_404(id)
    author = User.query.get(ex.author_id)
    final_code = re.sub(r"@@\s*(.*?)\s*@@", r"\1", ex.code_raw or "")
    return render_template(
        'cvicenie.html',
        exercise=ex, author=author,
        solution_clean=final_code,
        category_icon=category_icons.get(ex.category, "fas fa-code")
    )

@app.route('/moje-cvicenia')
@login_required
def moje_cvicenia():
    category    = request.args.get('category')
    subcategory = request.args.get('subcategory')

    q = Exercise.query.filter_by(author_id=current_user.id)
    if category: q = q.filter_by(category=category)
    if subcategory: q = q.filter_by(subcategory=subcategory)

    exercises = q.order_by(Exercise.id.desc()).all()
    return render_template('moje-cvicenia.html',
                           exercises=exercises,
                           selected_category=category,
                           selected_subcategory=subcategory)

@app.route('/cvicenie/<int:id>/publish')
@login_required
def publish_exercise(id):
    ex = Exercise.query.get_or_404(id)
    if ex.author_id != current_user.id:
        flash("Nemáš oprávnenie publikovať toto cvičenie.")
        return redirect(url_for('dashboard'))
    ex.published = True; db.session.commit()
    flash("Cvičenie bolo publikované!")
    return redirect(url_for('moje_cvicenia'))

@app.route('/cvicenie/<int:id>/edit', methods=['GET','POST'])
@login_required
def edit_exercise(id):
    ex = Exercise.query.get_or_404(id)
    if ex.author_id != current_user.id:
        flash("Nemáš oprávnenie upraviť toto cvičenie.")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        ex.title       = request.form['title']
        ex.category    = request.form['category']
        ex.subcategory = request.form['subcategory']
        ex.full_description = request.form['full_description']
        code_raw = request.form['code']
        ex.code = Markup(re.sub(
            r"@@\s*(.*?)\s*@@",
            r"<input type='text' class='code-input' data-answer='\1' style='width:70px;'>",
            code_raw or ''
        ))
        file = request.files.get('cover_image')
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join('static/uploads/covers', filename))
            ex.cover_image = filename
        db.session.commit()
        flash("Zmeny boli uložené.")
        return render_template('cvicenie.html', exercise=ex, author=current_user, is_preview=True)

    return render_template('nove.html', exercise=ex)

@app.route('/cvicenie/delete/<int:id>', methods=['POST'])
@login_required
def delete_exercise(id):
    ex = Exercise.query.get_or_404(id)
    if ex.author_id != current_user.id: abort(403)
    db.session.delete(ex); db.session.commit()
    flash('Cvičenie bolo vymazané.')
    return redirect(url_for('moje_cvicenia'))

# --------------------------------------------------------------------------- #
# OSTATNÉ STRÁNKY
# --------------------------------------------------------------------------- #

@app.route('/profil')
def profil():
    return render_template('profil.html')

@app.route('/objavujte')
def objavujte():
    category    = request.args.get('category')
    subcategory = request.args.get('subcategory')

    query = db.session.query(Exercise, User).join(User, Exercise.author_id == User.id)
    if category: query = query.filter(Exercise.category == category)
    if subcategory: query = query.filter(Exercise.subcategory == subcategory)
    exercises = query.all()

    rq = db.session.query(Exercise, User).join(User).filter(Exercise.published == True)
    if category: rq = rq.filter(Exercise.category == category)
    if subcategory: rq = rq.filter(Exercise.subcategory == subcategory)
    pool = rq.all()
    random_exercise = random.choice(pool) if pool else None

    return render_template('objavujte.html', exercises=exercises, random_exercise=random_exercise)

@app.route('/projekty')
def projekty():
    projects = (
        Project.query
        .filter_by(published=True)
        .order_by(Project.id.desc())
        .all()
    )
    return render_template('projekty.html', projects=projects)

@app.route('/projekty/<int:project_id>')
def projekt_public(project_id):
    p = Project.query.get_or_404(project_id)
    if not p.published:
        abort(404)

    rows = (ProjectStep.query
            .filter_by(project_id=p.id)
            .order_by(ProjectStep.order.asc()).all())

    steps_payload = []
    for r in rows:
        steps_payload.append({
            "title": r.title or "",
            "explain": r.explain or "",
            "bullets": (r.bullets or "").splitlines() if r.bullets else [],
            "checks": (r.checks or "").splitlines() if r.checks else [],
            "hint": r.hint or "",
            "file": r.file_name or "",
            "code": r.code or "",
            "added": [int(x) for x in (r.added_csv or "").split(",") if x.strip().isdigit()],
        })

    payload = {
        "meta": {
            "title": p.title,
            "level": p.level,
            "category": p.category,
            "time": p.time_estimate or "",
            "preview": p.preview_url or "",
            "langs": {k: True for k in (p.langs.split(",") if p.langs else []) if k.strip()},
            "assignment": p.assignment or "",
            "tips": p.tips or "",
            "icon_path": p.icon_path or None,
            "cover_path": p.cover_path or None,
        },
        "steps": steps_payload
    }

    # rovnaká šablóna ako interný detail – funguje aj public
    return render_template('projekt-html.html', project_payload=payload, is_public=True)


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

# --------------------------------------------------------------------------- #
# QUIZ API (skrátene – bez zmien oproti tvojmu)
# --------------------------------------------------------------------------- #

class QuizQuestion(db.Model):
    __tablename__ = 'quiz_questions'
    id         = db.Column(db.Integer, primary_key=True)
    author_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    category   = db.Column(db.String(50), nullable=False, index=True)
    subcategory= db.Column(db.String(100), nullable=True, index=True)
    question   = db.Column(db.Text, nullable=False)
    A          = db.Column(db.Text, nullable=False)
    B          = db.Column(db.Text, nullable=False)
    C          = db.Column(db.Text, nullable=False)
    D          = db.Column(db.Text, nullable=False)
    correct    = db.Column(db.String(1), nullable=False)  # 'A' | 'B' | 'C' | 'D'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    author = db.relationship('User', backref='quiz_questions')

    def to_dict(self):
        return {
            "id": self.id, "author_id": self.author_id,
            "category": self.category, "subcategory": self.subcategory or "",
            "question": self.question, "A": self.A, "B": self.B, "C": self.C, "D": self.D,
            "correct": self.correct,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

def _apply_scope(query, scope):
    return query if scope == 'all' else query.filter(QuizQuestion.author_id == (current_user.id if current_user.is_authenticated else -1))

def _validate_question_payload(data, is_update=False):
    required = ['category','subcategory','question','A','B','C','D','correct']
    if not is_update:
        for k in required:
            if not data.get(k): return f"Missing field: {k}"
    if data.get('correct') and data['correct'] not in ['A','B','C','D']:
        return "Field 'correct' must be one of A,B,C,D"
    return None

@app.route('/api/questions', methods=['GET','POST'])
@login_required
def api_questions():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        err = _validate_question_payload(data)
        if err: return jsonify({"error": err}), 400
        q = QuizQuestion(
            author_id=current_user.id,
            category=data['category'], subcategory=data.get('subcategory') or "",
            question=data['question'].strip(),
            A=data['A'].strip(), B=data['B'].strip(), C=data['C'].strip(), D=data['D'].strip(),
            correct=data['correct']
        )
        db.session.add(q); db.session.commit()
        return jsonify({"item": q.to_dict()}), 201

    scope      = request.args.get('scope','mine')
    category   = request.args.get('category')
    subcategory= request.args.get('subcategory')
    search     = request.args.get('search')
    page       = request.args.get('page', type=int)
    page_size  = request.args.get('page_size', type=int, default=10)
    limit      = request.args.get('limit', type=int)
    random_flag= request.args.get('random', default='0') in ['1','true','True']

    q = _apply_scope(QuizQuestion.query, scope)
    if category and category != '__all__': q = q.filter(QuizQuestion.category == category)
    if subcategory and subcategory != '__all__': q = q.filter(QuizQuestion.subcategory == subcategory)
    if search: q = q.filter(QuizQuestion.question.ilike(f"%{search}%"))
    if random_flag: q = q.order_by(func.random())

    if page:
        page = max(1, page); page_size = max(1, min(50, page_size))
        total = q.count()
        items = q.order_by(QuizQuestion.id.desc()).offset((page-1)*page_size).limit(page_size).all()
        return jsonify({"items":[it.to_dict() for it in items], "total": total, "page": page, "page_size": page_size})
    elif limit:
        limit = max(1, min(200, limit))
        items = q.limit(limit).all()
        return jsonify({"items":[it.to_dict() for it in items], "total": len(items)})
    else:
        items = q.order_by(QuizQuestion.id.desc()).limit(1000).all()
        return jsonify({"items":[it.to_dict() for it in items], "total": len(items)})

@app.route('/api/questions/<int:q_id>', methods=['GET','PUT','DELETE'])
@login_required
def api_question_detail(q_id):
    q = QuizQuestion.query.get_or_404(q_id)
    if request.method in ['PUT','DELETE'] and q.author_id != current_user.id:
        return jsonify({"error":"Nemáš oprávnenie upravovať alebo mazať túto otázku."}), 403
    if request.method == 'GET':
        if q.author_id != current_user.id:
            return jsonify({"error":"Nedostupné."}), 403
        return jsonify({"item": q.to_dict()})
    if request.method == 'PUT':
        data = request.get_json(silent=True) or {}
        err = _validate_question_payload(data, is_update=True)
        if err: return jsonify({"error": err}), 400
        q.category    = data.get('category', q.category)
        q.subcategory = data.get('subcategory', q.subcategory)
        q.question    = data.get('question', q.question)
        q.A = data.get('A', q.A); q.B = data.get('B', q.B); q.C = data.get('C', q.C); q.D = data.get('D', q.D)
        if data.get('correct') in ['A','B','C','D']: q.correct = data['correct']
        db.session.commit(); return jsonify({"item": q.to_dict()})
    db.session.delete(q); db.session.commit()
    return jsonify({"status":"deleted","id":q_id})

@app.route('/api/subcategories')
@login_required
def api_subcategories():
    scope    = request.args.get('scope','mine')
    category = request.args.get('category')
    q = _apply_scope(QuizQuestion.query, scope)
    if category and category != '__all__': q = q.filter(QuizQuestion.category == category)
    subs = q.with_entities(QuizQuestion.subcategory).distinct().all()
    return jsonify({"subcategories":[s[0] for s in subs if s[0]]})

@app.route('/kviz-vsetci')
def kviz_vsetci():
    return render_template('kviz-vsetci.html', user=current_user)

# --------------------------------------------------------------------------- #
# PROJEKTY – builder / upload / publish / list / detail
# --------------------------------------------------------------------------- #

@app.route('/projekt/vytvorit')
@login_required
def projekt_vytvorit():
    return render_template('projekt-vytvorit.html')

# alias (ak niekde voláš projekty_vytvorit)
app.add_url_rule('/projekty/vytvorit', endpoint='projekty_vytvorit', view_func=projekt_vytvorit)

# statická stránka – používaná pre PREVIEW (ťahá payload z localStorage)
@app.route('/projekty/html')
def projekt_html():
    return render_template('projekt-html.html', project_payload=None)

@app.route('/api/upload/project-image', methods=['POST'], endpoint='api_upload_project_image')
@login_required
def api_upload_project_image():
    try:
        file = request.files.get('file')
        kind = request.form.get('kind','cover')
        rel_path = _save_project_image(file, kind=kind)
        return jsonify({"ok": True, "path": rel_path})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@app.route('/projekt/publish', methods=['POST'])
@login_required
def projekt_publish():
    data = request.get_json(silent=True) or {}
    meta = data.get("meta") or {}
    steps_payload = data.get("steps") or []

    try:
        pr = Project(
            author_id=current_user.id,
            title=meta.get("title") or "Bez názvu",
            level=meta.get("level") or "Začiatočník",
            category=meta.get("category") or "Iné",
            time_estimate=meta.get("time") or "",
            preview_url=meta.get("preview") or "",
            langs=",".join([k for k,v in (meta.get("langs") or {}).items() if v]),
            icon_path=meta.get("icon_path") or None,
            cover_path=meta.get("cover_path") or None,
            steps_count=len(steps_payload),
            assignment=meta.get("assignment") or "",
            tips=meta.get("tips") or "",
            published=True,
        )
        db.session.add(pr); db.session.flush()  # pr.id

        for i, s in enumerate(steps_payload):
            db.session.add(ProjectStep(
                project_id=pr.id,
                order=i,
                title=s.get("title") or "",
                explain=s.get("explain") or "",
                bullets="\n".join(s.get("bullets") or []),
                checks="\n".join(s.get("checks") or []),
                hint=s.get("hint") or "",
                file_name=s.get("file") or "",
                code=s.get("code") or "",
                added_csv=",".join([str(n) for n in (s.get("added") or [])]),
            ))

        db.session.commit()
        flash("Projekt bol publikovaný!")
        return jsonify({"ok": True, "project_id": pr.id, "redirect": url_for('moje_projekty')})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400

# (voliteľné) preview cez session – ak by si raz chcela
@app.route('/projekt/preview', methods=['POST'])
@login_required
def projekt_preview():
    data = request.get_json(silent=True) or {}
    session['project_preview'] = data
    return jsonify({"ok": True, "redirect": url_for('projekt_nahlad')})

@app.route('/projekt/nahlad')
@login_required
def projekt_nahlad():
    payload = session.get('project_preview')
    if not payload:
        flash("Chýba náhľad – skús to znova z buildera.")
        return redirect(url_for('projekt_vytvorit'))
    return render_template('projekt-html.html', is_preview=True, project_payload=payload, payload=payload)

# DETAIL – kľúčová zmena: posielame payload do šablóny (žiadny fallback)
@app.route('/projekt/<int:project_id>')
@login_required
def projekt_detail(project_id):
    p = Project.query.get_or_404(project_id)
    if p.author_id != current_user.id:
        flash("Projekt nie je dostupný.")
        return redirect(url_for('moje_projekty'))

    rows = ProjectStep.query.filter_by(project_id=p.id).order_by(ProjectStep.order.asc()).all()

    steps_payload = []
    for r in rows:
        steps_payload.append({
            "title": r.title or "",
            "explain": r.explain or "",
            "bullets": (r.bullets or "").splitlines() if r.bullets else [],
            "checks": (r.checks or "").splitlines() if r.checks else [],
            "hint": r.hint or "",
            "file": r.file_name or "",
            "code": r.code or "",
            "added": _ints_from_csv(r.added_csv),
        })

    payload = {
        "meta": {
            "title": p.title,
            "level": p.level,
            "category": p.category,
            "time": p.time_estimate or "",
            "preview": p.preview_url or "",
            "langs": _flags_from_csv(p.langs),
            "assignment": p.assignment or "",
            "tips": p.tips or "",
            "icon_path": p.icon_path or None,
            "cover_path": p.cover_path or None,
        },
        "steps": steps_payload
    }

    # DÔLEŽITÉ: pošli payload do šablóny (šablóna si ho dá do window.__PROJECT_DATA__)
    return render_template('projekt-html.html', project_payload=payload)

@app.route('/moje-projekty')
@login_required
def moje_projekty():
    projects = Project.query.filter_by(author_id=current_user.id).order_by(Project.id.desc()).all()
    return render_template('moje-projekty.html', projects=projects)

@app.route('/projekt/<int:project_id>/delete', methods=['POST'])
@login_required
def projekt_delete(project_id):
    p = Project.query.get_or_404(project_id)
    if p.author_id != current_user.id:
        flash("Nemáš oprávnenie odstrániť tento projekt.")
        return redirect(url_for('moje_projekty'))
    db.session.delete(p); db.session.commit()
    flash("Projekt bol odstránený.")
    return redirect(url_for('moje_projekty'))

@app.route('/_debug/projects_schema')
def _debug_projects_schema():
    rows = db.session.execute(text("""
      select table_name, column_name
      from information_schema.columns
      where table_name in ('projects','project_steps')
      order by table_name, ordinal_position
    """)).fetchall()
    return jsonify({"columns":[(r[0], r[1]) for r in rows]})

# --------------------------------------------------------------------------- #
# MAIN
# --------------------------------------------------------------------------- #

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
