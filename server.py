from contextlib import contextmanager
import logging

import os 
import json
from urllib.parse import quote_plus, urlencode
from authlib.integrations.flask_client import OAuth
from dotenv import find_dotenv, load_dotenv
from flask import current_app, g, Flask, render_template, request, session, redirect, url_for


import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import DictCursor

pool = None


##### AUTH STUFF ######

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

app = Flask(__name__)
app.secret_key = os.environ['FLASK_SECRET']

oauth = OAuth(app)

oauth.register(
    "auth0",
    client_id=os.environ.get("AUTH0_CLIENT_ID"),
    client_secret=os.environ.get("AUTH0_CLIENT_SECRET"),
    client_kwargs={
        "scope": "openid profile email",
    },
    server_metadata_url=f'https://{os.environ.get("AUTH0_DOMAIN")}/.well-known/openid-configuration'
)

@app.route("/login")
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )

@app.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    session["user"] = token
    return redirect(url_for("hello"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://" + os.environ.get("AUTH0_DOMAIN")
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": url_for("home", _external=True),
                "client_id": os.environ.get("AUTH0_CLIENT_ID"),
            },
            quote_via=quote_plus,
        )
    )

##### END OF AUTH STUFF ######

@app.route('/')
@app.route('/<name>')
def hello(name=None):
    if name:
        session["name"] = name
    return render_template('hello.html', name=session.get("name"))

def setup():
    global pool
    DATABASE_URL = os.environ['DATABASE_URL']
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable not set")
    #current_app.logger.info(f"creating db connection pool")
    pool = ThreadedConnectionPool(1, 100, dsn=DATABASE_URL, sslmode='require')
    print("Database connection pool created.")



@contextmanager
def get_db_connection():
    try:
        connection = pool.getconn()
        yield connection
    finally:
        pool.putconn(connection)


@contextmanager
def get_db_cursor(commit=False):
    with get_db_connection() as connection:
      cursor = connection.cursor(cursor_factory=DictCursor)
      # cursor = connection.cursor()
      try:
          yield cursor
          if commit:
              connection.commit()
      finally:
          cursor.close()

def add_person(first, last, phone):
    # Since we're using connection pooling, it's not as big of a deal to have
    # lots of short-lived cursors (I think -- worth testing if we ever go big)
    with get_db_cursor(True) as cur:
        cur.execute("INSERT INTO users (firstname, lastname, phone) values (%s, %s, %s)", (first, last, phone))


setup()


def get_people():
    retval = []
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM users")
        for row in cur:
            retval.append({
                "firstname": row["firstname"],
                "lastname": row["lastname"],
                "phone": row["phone"]
            })
    return retval


@app.route("/submit_form", methods=["POST"])
def submit_form():
    firstname = request.form.get("firstname")
    lastname = request.form.get("lastname")
    phone = request.form.get("phone")

    add_person(firstname, lastname, int(phone))

    guest = get_people()
    return render_template('guest.html', name=None, guest=guest)

# <--------------------auth0----------------------->

