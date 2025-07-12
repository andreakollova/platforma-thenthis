from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/cvicenia')
def cvicenia():
    return render_template('cvicenia.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/nove')
def nove():
    return render_template('nove.html')

@app.route('/moje-cvicenia')
def moje_cvicenia():
    return render_template('moje-cvicenia.html')

@app.route('/profil')
def profil():
    return render_template('profil.html')

@app.route('/objavujte')
def objavujte():
    return render_template('objavujte.html')

@app.route("/register")
def register():
    return render_template("register.html")

if __name__ == '__main__':
    app.run(debug=True)
