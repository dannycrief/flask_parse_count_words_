from datetime import datetime
import os
import requests
import enum
from sqlalchemy import Enum
from celery import Celery
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template, request
import logging

logging.basicConfig(filename="app.log", level=logging.INFO, format="%(levelname)s: %(message)s")

DB_URL = 'postgresql+psycopg2://{user}:{pw}@{url}/{db}'.format(user=os.environ.get('POSTGRES_USER', 'postgres'),
                                                               pw=os.environ.get('POSTGRES_PW', '211217ns'),
                                                               url=os.environ.get('POSTGRES_URL', '127.0.0.1:5432'),
                                                               db=os.environ.get('POSTGRES_DB', 'parsing_site'))

app = Flask(__name__)
app.debug = True
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
celery = Celery(app.name, broker='redis://localhost', backend='db+' + DB_URL)


class TaskStatus(enum.Enum):
    NOT_STARTED = 1
    PENDING = 2
    FINISHED = 3


class Tasks(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(300), unique=False, nullable=True)
    timestamp = db.Column(db.DateTime())
    task_status = db.Column(Enum(TaskStatus))
    http_status = db.Column(db.Integer)
    results = db.relationship('Results', uselist=False, back_populates="tasks")


class Results(db.Model):
    __tablename__ = 'results'
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(300), unique=False, nullable=True)
    words_count = db.Column(db.Integer, unique=False, nullable=True)
    http_status_code = db.Column(db.Integer)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))
    tasks = db.relationship("Tasks", back_populates="results")


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        app.logger.info("Found GET method")
        return render_template('index.html')
    elif request.method == "POST":
        app.logger.debug("Found method POST")
        received_link = request.form['receivedLink']
        app.logger.debug("Got link: %s" % received_link)
        if received_link != '':
            app.logger.debug("Received link is not empty")
            if not received_link.startswith('http') or not received_link.startswith('https'):
                received_link = 'http://' + received_link
            session = Tasks(address=received_link, timestamp=datetime.now(), task_status='NOT_STARTED')
            db.session.add(session)
            db.session.commit()
            parsing_func.apply_async([session.id], countdown=3, expires=10)
        return render_template('index.html')


@celery.task
def parsing_func(_id):
    task = Tasks.query.get(_id)
    task.task_status = 'PENDING'
    app.logger.info("Task status: PENDING")
    db.session.commit()
    address = task.address
    with app.app_context():
        parse_url = requests.get(address)
        parse_status = parse_url.status_code
        app.logger.error("Status: %s" % parse_status)
        if parse_url.ok:
            parse_url = parse_url.text.lower().split()
            words = parse_url.count('python')
        task = Tasks.query.get(_id)
        result = Results(address=address, words_count=words,
                         http_status_code=parse_status, task_id=task.id)
        task.http_status = int(parse_status)
        task.task_status = 'FINISHED'
        db.session.add(result)
        db.session.commit()
        app.logger.info("Task status: FINISHED and successfully committed")


@app.route('/results')
def show_results():
    results = Results.query.all()
    for i in results:
        if not i.address or i.address == "https" or i.address == "http":
            app.logger.warning("Address is emtpy: %s" % i.address)
        if i.http_status_code != 200:
            app.logger.error("Status code is different. {} - code: {}".format(i.address, i.http_status_code))
        if i.words_count == 0:
            app.logger.warning("Words count is zero. Check it out: {} count is: {}".format(i.address, i.words_count))
    return render_template('result.html', results=results)


@app.cli.command('resetdb')
def resetdb_command():
    from sqlalchemy_utils import database_exists, create_database, drop_database

    if database_exists(DB_URL):
        app.logger.warning("Deleting database")
        drop_database(DB_URL)

    if not database_exists(DB_URL):
        app.logger.info("Creating database.")
        create_database(DB_URL)

    app.logger.info("Creating tables.")
    db.create_all()


if __name__ == '__main__':
    app.run(debug=True)
