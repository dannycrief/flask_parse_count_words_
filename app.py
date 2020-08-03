from datetime import datetime
import os
import requests
import enum
from sqlalchemy import Enum
from celery import Celery
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template, request, redirect, url_for
import json
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired


class FormCheck(FlaskForm):
    address = StringField('address', validators=[DataRequired()])


app = Flask(__name__)

app.debug = True
app.config["SQLALCHEMY_DATABASE_URI"] = 'postgresql+psycopg2://postgres:211217ns@postgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'so-secret-dont-you-dare-to-tell-somebody'

celery = Celery(app.name, broker=os.getenv("CELERY_BROKER_URL", "redis://redis-container"),
                backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis-container"))
db = SQLAlchemy(app)

port = int(os.getenv('PORT', 5000))


class Results(db.Model):
    id = db.Column('ID', db.Integer, primary_key=True, autoincrement=True, nullable=False)
    address = db.Column(db.String(300), unique=False, nullable=True)
    words_count = db.Column(db.Integer, unique=False, nullable=True)
    http_status_code = db.Column(db.Integer)


class TaskStatus(enum.Enum):
    NOT_STARTED = 1
    PENDING = 2
    FINISHED = 3


class Tasks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(300), unique=False, nullable=True)
    timestamp = db.Column(db.DateTime())
    task_status = db.Column(Enum(TaskStatus))
    http_status = db.Column(db.Integer)


class NSQD:
    def __init__(self, server):
        self.server = "http://{server}/pub".format(server=server)

    def send(self, topic, message):
        res = requests.post(self.server, params={'topic': topic}, data=message)
        if res.ok:
            return res


nsqd = NSQD('nsqd:4151')


@app.route('/', methods=['GET', 'POST'])
def index():
    formHTML = FormCheck()
    if request.method == 'GET':
        return render_template('index.html', form=formHTML)
    elif request.method == "POST":
        if formHTML.validate_on_submit():
            received_link = request.form.get('address')
            task = Tasks(address=received_link, timestamp=datetime.now(), task_status='NOT_STARTED')
            db.session.add(task)
            db.session.commit()
            get_link.delay(task.id)
            return redirect(url_for('show_results'))
        error = 'Your form is fucked up: form validation ERROR'
        return render_template('error.html', form=formHTML, error=error)
    return render_template('index.html', form=formHTML)


@celery.task
def get_link(id):
    task = Tasks.query.get(id)
    task.task_status = 'PENDING'
    db.session.commit()
    address = task.address
    if not (address.startswith('http') or address.startswith('https')):
        address = 'http://' + address
    nsqd.send('parsed_data', json.dumps({"address": address, "id": str(id)}))


@celery.task
def get_word_count(id, address):
    count = 0
    try:
        res = requests.get(address, timeout=10)
        status = res.status_code
        if res.ok:
            words = res.text.lower().split()
            count = words.count('python')
    except requests.RequestException:
        status = 400
    result = Results(address=address, words_count=count, http_status_code=status)
    task = Tasks.query.get(id)
    task.task_status = 'FINISHED'
    db.session.add(result)
    db.session.commit()


@app.route('/results')
def show_results():
    results = Results.query.all()
    for i in results:
        if not i.address or i.address == "https" or i.address == "http":
            print("Address is emtpy: %s" % i.address)
        if i.http_status_code != 200:
            print("Status code is different. {} - code: {}".format(i.address, i.http_status_code))
        if i.words_count == 0:
            print("Words count is zero. Check it out: {} count is: {}".format(i.address, i.words_count))
    return render_template('result.html', results=results)


if __name__ == '__main__':
    db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
