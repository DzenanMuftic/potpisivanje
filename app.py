from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
from datetime import datetime
from sqlalchemy.orm import aliased  # Add this import


app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:4Banana$@localhost/wf'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class Users(UserMixin, db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)

    def get_id(self):
        return str(self.user_id)

class Tasks(db.Model):
    __tablename__ = 'tasks'
    task_id = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.String(255), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    created_by = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Add this line

class TaskStatuses(db.Model):
    __tablename__ = 'task_statuses'
    status_id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.task_id'))
    status = db.Column(db.String(50), nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = Users.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        file = request.files['file']
        if file:
            filename = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            flash('File successfully uploaded')
            return redirect(url_for('delegate'))  # Redirect to delegate page
    return render_template('upload.html')

@app.route('/delegate', methods=['GET', 'POST'])
@login_required
def delegate():
    if request.method == 'POST':
        task_name = request.form['task_name']
        assigned_to = request.form['assigned_to']
        new_task = Tasks(task_name=task_name, assigned_to=assigned_to, created_by=current_user.user_id)
        db.session.add(new_task)
        db.session.commit()
        flash('Task successfully delegated')
        return redirect(url_for('dashboard'))
    users = Users.query.all()
    return render_template('delegate.html', users=users)


@app.route('/dashboard')
@login_required
def dashboard():
    # Create aliases for the users table
    creator_alias = aliased(Users)
    updater_alias = aliased(Users)

    # Fetch open tasks delegated to the current user
    user_tasks = db.session.query(
        Tasks.task_id,
        Tasks.task_name,
        Tasks.created_at,
        creator_alias.username.label('created_by_username'),
        TaskStatuses.status,
        updater_alias.username.label('updated_by_username')
    ).join(creator_alias, Tasks.created_by == creator_alias.user_id)\
     .outerjoin(TaskStatuses, Tasks.task_id == TaskStatuses.task_id)\
     .outerjoin(updater_alias, TaskStatuses.updated_by == updater_alias.user_id)\
     .filter(Tasks.assigned_to == current_user.user_id)\
     .filter((TaskStatuses.status != 'Closed') | (TaskStatuses.status.is_(None)))\
     .all()
    return render_template('dashboard.html', tasks=user_tasks)



@app.route('/close_task/<int:task_id>', methods=['POST'])
@login_required
def close_task(task_id):
    task = Tasks.query.get(task_id)
    if task:
        new_status = TaskStatuses(task_id=task_id, status='Closed', updated_by=current_user.user_id)
        db.session.add(new_status)
        db.session.commit()
        flash('Task closed')
    return redirect(url_for('dashboard'))


@app.route('/report')
@login_required
def report():
    # Create aliases for the users table
    creator_alias = aliased(Users)
    updater_alias = aliased(Users)

    # Fetch all tasks with their statuses and related user information, sorted by created_at (newest first)
    tasks_report = db.session.query(
        Tasks.task_id,
        Tasks.task_name,
        Tasks.created_at,
        creator_alias.username.label('created_by_username'),
        TaskStatuses.status,
        updater_alias.username.label('updated_by_username')
    ).join(creator_alias, Tasks.created_by == creator_alias.user_id)\
     .outerjoin(TaskStatuses, Tasks.task_id == TaskStatuses.task_id)\
     .outerjoin(updater_alias, TaskStatuses.updated_by == updater_alias.user_id)\
     .order_by(Tasks.created_at.desc())\
     .all()
    return render_template('report.html', tasks=tasks_report)

if __name__ == '__main__':
    app.run(debug=True)