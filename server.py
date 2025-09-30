from contextlib import contextmanager
import logging
import os

from flask import current_app, g, Flask, render_template, request

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import DictCursor

pool = None

app = Flask(__name__)


@app.route('/')
@app.route('/<name>')
def hello(name=None):
    return render_template('hello.html', name=name)

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


