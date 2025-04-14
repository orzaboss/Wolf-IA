from flask import Flask, request, render_template, redirect, url_for, session, jsonify
import mysql.connector
import bcrypt
import requests

app = Flask(__name__)
app.secret_key = "clave_super_secreta"

API_KEY = "AIzaSyBKTAnIJfC5pyUOSOeTYg3RBpzF_gj5UyM"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

contexto_wolfai = """
Tu nombre es WolfAi. Fuiste entrenado por estudiantes del TecNM de Mérida.
Eres un asistente diseñado para apoyar a estudiantes en su camino académico
"""

def conectar():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="wolfai"
    )

# ------------------ REGISTRO ------------------

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        correo = request.form['correo']
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        password = request.form['password']

        if len(password) < 6:
            return "La contraseña debe tener al menos 6 caracteres."

        hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        conn = conectar()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO usuarios (correo, nombre, apellido, password) VALUES (%s, %s, %s, %s)",
                           (correo, nombre, apellido, hash))
            conn.commit()
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            return "Ese correo ya está registrado."
        finally:
            cursor.close()
            conn.close()

    return render_template("registro.html")

# ------------------ LOGIN ------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        correo = request.form['correo']
        password = request.form['password']

        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT password, nombre FROM usuarios WHERE correo = %s", (correo,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result and bcrypt.checkpw(password.encode('utf-8'), result[0].encode('utf-8')):
            session['usuario'] = correo
            session['nombre'] = result[1]
            session['mensaje_count'] = 0
            return redirect(url_for('index'))
        else:
            error = "El correo o la contraseña deben de tener un error ortográfico o no se ha registrado."

    return render_template("login.html", error=error)

# ------------------ LOGOUT ------------------

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ------------------ INICIO ------------------

@app.route('/')
def index():
    nombre = session.get("nombre")
    return render_template("index.html", nombre=nombre)

# ------------------ CHAT ------------------

@app.route('/chat', methods=['POST'])
def chat():
    if "mensaje_count" not in session:
        session["mensaje_count"] = 0

    # Solo usuarios no logueados tienen límite de mensajes
    if "usuario" not in session and session["mensaje_count"] >= 5:
        return jsonify({"bloqueado": True})

    data = request.get_json()
    mensaje_usuario = data.get("message", "")

    contenidos = [{"role": "user", "parts": [{"text": contexto_wolfai}]}]

    # Agregar profesores desde DB si se pide
    if any(p in mensaje_usuario.lower() for p in ["profesores", "especialidad", "mentores"]):
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT nombre, especialidad, grado_academico FROM profesores")
        datos = cursor.fetchall()
        cursor.close()
        conn.close()
        profesores = "\n".join([f"- {n} ({g}): {e}" for n, e, g in datos])
        contenidos.append({"role": "user", "parts": [{"text": profesores}]})

    contenidos.append({"role": "user", "parts": [{"text": mensaje_usuario}]})

    headers = {"Content-Type": "application/json"}
    body = {
        "contents": contenidos,
        "generationConfig": {"temperature": 0.7}
    }

    response = requests.post(f"{API_URL}?key={API_KEY}", headers=headers, json=body)

    if response.status_code == 200:
        try:
            respuesta = response.json()['candidates'][0]['content']['parts'][0]['text']
        except:
            respuesta = "Lo siento, no pude entender la respuesta."
    else:
        respuesta = "Error al contactar con Gemini."

    # Solo aumenta el contador si NO está logueado
    if "usuario" not in session:
        session["mensaje_count"] += 1

    return jsonify({"response": respuesta, "bloqueado": False})

if __name__ == '__main__':
    app.run(debug=True)
