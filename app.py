from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
import psycopg2
import hashlib

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = '13f6e15b81e105a51c736c401d1ff2ffd1eed5189a338077c918d2edf3cb7cf7'
jwt = JWTManager(app)

mydb = psycopg2.connect(
    dbname="db", user="user", password="password", host="localhost", port="5432"
)

mycursor = mydb.cursor()

mycursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
)
""")
mydb.commit()

@app.route('/register', methods=['POST'])
def signup():
    info = request.json
    name = info['username']
    passw = hashlib.sha256(info['password'].encode()).hexdigest()

    try:
        mycursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (name, passw))
        mydb.commit()
        return jsonify(message="registered"), 201
    except:
        return jsonify(message="user exists"), 409

@app.route('/login', methods=['POST'])
def signin():
    data = request.json
    name = data['username']
    passw = hashlib.sha256(data['password'].encode()).hexdigest()

    try:
        mycursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (name, passw))
        user = mycursor.fetchone()

        if user:
            mytoken = create_access_token(identity=name)
            return jsonify(token=mytoken), 200
        else:
            return jsonify(msg="wrong login"), 401
    except Exception as e:
        mydb.rollback()
        return jsonify(error=str(e)), 500

@app.route('/users', methods=['GET'])
def show_users():
    try:
        mycursor.execute("SELECT username FROM users")
        names = mycursor.fetchall()
        return jsonify([n[0] for n in names]), 200
    except Exception as e:
        mydb.rollback()
        return jsonify(error=str(e)), 500

if __name__ == '__main__':
    app.run(debug=True)
