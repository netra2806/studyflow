from flask import Flask, render_template, request, jsonify, g
import sqlite3, os
from datetime import date, datetime, timedelta

app = Flask(__name__)
DB = os.path.join(app.root_path, 'database', 'studyflow.db')
os.makedirs(os.path.dirname(DB), exist_ok=True)

def db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_):
    conn = g.pop('db', None)
    if conn: conn.close()

def init_db():
    c = sqlite3.connect(DB)
    c.executescript('''
    CREATE TABLE IF NOT EXISTS subjects(id INTEGER PRIMARY KEY, name TEXT NOT NULL, color TEXT NOT NULL DEFAULT '#8d78df', description TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT DEFAULT '', subject_id INTEGER, category TEXT DEFAULT 'Assignments', priority TEXT DEFAULT 'Medium', due_date TEXT, duration REAL DEFAULT 1, done INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(subject_id) REFERENCES subjects(id));
    CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY, title TEXT NOT NULL, subject_id INTEGER, day TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL, notes TEXT DEFAULT '', done INTEGER DEFAULT 0, FOREIGN KEY(subject_id) REFERENCES subjects(id));
    CREATE TABLE IF NOT EXISTS pomodoros(id INTEGER PRIMARY KEY, minutes REAL NOT NULL, completed_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, title TEXT NOT NULL, kind TEXT DEFAULT 'Reminder', day TEXT NOT NULL, notes TEXT DEFAULT '');
    ''')
    if not c.execute('SELECT 1 FROM subjects LIMIT 1').fetchone():
        c.executemany('INSERT INTO subjects(name,color,description) VALUES(?,?,?)', [('Biology','#8d78df','Cell systems & genetics'),('Mathematics','#e5a765','Calculus and problem solving'),('Literature','#6fa58b','Reading and critical writing')])
        c.executemany('INSERT INTO tasks(title,subject_id,category,priority,due_date,duration) VALUES(?,?,?,?,?,?)', [
            ('Review cell division notes',1,'Revision','High',date.today().isoformat(),1.5),('Problem set 06 — integrals',2,'Assignments','Medium',(date.today()+timedelta(days=2)).isoformat(),2),('Read chapters 4–5',3,'Revision','Low',(date.today()+timedelta(days=4)).isoformat(),1)])
        c.executemany('INSERT INTO sessions(title,subject_id,day,start,end,notes) VALUES(?,?,?,?,?,?)', [('Deep work: cell division',1,date.today().isoformat(),'09:00','10:30','Use active recall'),('Integral practice',2,date.today().isoformat(),'11:00','12:00','Work through set 06')])
    c.commit(); c.close()

def rows(sql, args=()): return [dict(x) for x in db().execute(sql,args).fetchall()]
def one(sql,args=()):
    x=db().execute(sql,args).fetchone(); return dict(x) if x else None

@app.get('/')
def home(): return render_template('index.html')

@app.get('/api/data')
def data():
    today=date.today().isoformat(); start=(date.today()-timedelta(days=date.today().weekday())).isoformat(); end=(date.today()+timedelta(days=6-date.today().weekday())).isoformat()
    completed=db().execute('SELECT COUNT(*) FROM tasks WHERE done=1').fetchone()[0]
    pending=db().execute('SELECT COUNT(*) FROM tasks WHERE done=0').fetchone()[0]
    hours=db().execute("SELECT COALESCE(SUM((CAST(substr(end,1,2) AS INT)*60+CAST(substr(end,4,2) AS INT)-CAST(substr(start,1,2) AS INT)*60-CAST(substr(start,4,2) AS INT))/60.0),0) FROM sessions WHERE done=1").fetchone()[0]
    week_hours=db().execute("SELECT COALESCE(SUM((CAST(substr(end,1,2) AS INT)*60+CAST(substr(end,4,2) AS INT)-CAST(substr(start,1,2) AS INT)*60-CAST(substr(start,4,2) AS INT))/60.0),0) FROM sessions WHERE done=1 AND day BETWEEN ? AND ?",(start,end)).fetchone()[0]
    week_tasks=db().execute('SELECT COUNT(*) FROM tasks WHERE done=1 AND substr(created_at,1,10) BETWEEN ? AND ?',(start,end)).fetchone()[0]
    byday=[]
    for i in range(7):
        d=date.today()-timedelta(days=date.today().weekday()-i); byday.append({'day':d.strftime('%a'),'hours':round(db().execute("SELECT COALESCE(SUM((CAST(substr(end,1,2) AS INT)*60+CAST(substr(end,4,2) AS INT)-CAST(substr(start,1,2) AS INT)*60-CAST(substr(start,4,2) AS INT))/60.0),0) FROM sessions WHERE done=1 AND day=?",(d.isoformat(),)).fetchone()[0],1)})
    subs=rows('SELECT s.*, (SELECT COALESCE(SUM((CAST(substr(end,1,2) AS INT)*60+CAST(substr(end,4,2) AS INT)-CAST(substr(start,1,2) AS INT)*60-CAST(substr(start,4,2) AS INT))/60.0),0) FROM sessions WHERE subject_id=s.id AND done=1) hours, (SELECT COUNT(*) FROM tasks WHERE subject_id=s.id AND done=1) done_tasks, (SELECT COUNT(*) FROM tasks WHERE subject_id=s.id) task_count FROM subjects s ORDER BY s.id')
    focus=db().execute('SELECT COUNT(*) FROM pomodoros').fetchone()[0]
    return jsonify(tasks=rows('SELECT t.*,s.name subject,s.color FROM tasks t LEFT JOIN subjects s ON s.id=t.subject_id ORDER BY done,due_date'), subjects=subs, sessions=rows('SELECT x.*,s.name subject,s.color FROM sessions x LEFT JOIN subjects s ON s.id=x.subject_id ORDER BY day,start'), events=rows('SELECT * FROM events ORDER BY day'), stats={'completed':completed,'pending':pending,'hours':round(hours,1),'weekHours':round(week_hours,1),'weekTasks':week_tasks,'focus':focus,'productivity':round(completed*100/max(completed+pending,1))}, weekly=byday, today=today)

@app.post('/api/tasks')
def add_task():
    v=request.get_json(); title=(v.get('title') or '').strip()
    if not title: return jsonify(error='Add a task title first.'),400
    cur=db().execute('INSERT INTO tasks(title,description,subject_id,category,priority,due_date,duration) VALUES(?,?,?,?,?,?,?)',(title,v.get('description',''),v.get('subject_id') or None,v.get('category','Assignments'),v.get('priority','Medium'),v.get('due_date') or None,float(v.get('duration') or 1)))
    db().commit(); return jsonify(id=cur.lastrowid)

@app.patch('/api/tasks/<int:id>')
def update_task(id):
    v=request.get_json(); allowed={'title','description','subject_id','category','priority','due_date','duration','done'}
    fields=[(k,v[k]) for k in v if k in allowed]
    if not fields:return jsonify(error='No changes provided.'),400
    db().execute('UPDATE tasks SET '+','.join(k+'=?' for k,_ in fields)+' WHERE id=?',[x[1] for x in fields]+[id]); db().commit(); return jsonify(ok=True)

@app.delete('/api/tasks/<int:id>')
def delete_task(id): db().execute('DELETE FROM tasks WHERE id=?',(id,)); db().commit(); return jsonify(ok=True)

@app.post('/api/subjects')
def add_subject():
    v=request.get_json(); name=(v.get('name') or '').strip()
    if not name:return jsonify(error='A subject name is required.'),400
    cur=db().execute('INSERT INTO subjects(name,color,description) VALUES(?,?,?)',(name,v.get('color','#8d78df'),v.get('description',''))); db().commit(); return jsonify(id=cur.lastrowid)

@app.post('/api/sessions')
def add_session():
    v=request.get_json(); day=v.get('day'); start=v.get('start'); end=v.get('end'); title=(v.get('title') or '').strip()
    if not all([day,start,end,title]):return jsonify(error='Fill in the title, date and both times.'),400
    if start>=end:return jsonify(error='End time must be after start time.'),400
    clash=one('SELECT id FROM sessions WHERE day=? AND start < ? AND end > ?',(day,end,start))
    if clash:return jsonify(error='That time overlaps another study session.'),409
    cur=db().execute('INSERT INTO sessions(title,subject_id,day,start,end,notes) VALUES(?,?,?,?,?,?)',(title,v.get('subject_id') or None,day,start,end,v.get('notes',''))); db().commit(); return jsonify(id=cur.lastrowid)

@app.patch('/api/sessions/<int:id>')
def update_session(id):
    v=request.get_json(); db().execute('UPDATE sessions SET done=? WHERE id=?',(int(bool(v.get('done'))),id)); db().commit(); return jsonify(ok=True)

@app.delete('/api/sessions/<int:id>')
def delete_session(id): db().execute('DELETE FROM sessions WHERE id=?',(id,)); db().commit(); return jsonify(ok=True)

@app.post('/api/pomodoros')
def pomodoro():
    minutes=float(request.get_json().get('minutes',25)); db().execute('INSERT INTO pomodoros(minutes) VALUES(?)',(minutes,)); db().commit(); return jsonify(ok=True)

@app.post('/api/events')
def add_event():
    v=request.get_json(); title=(v.get('title') or '').strip()
    if not title or not v.get('day'):return jsonify(error='Add an event title and date.'),400
    cur=db().execute('INSERT INTO events(title,kind,day,notes) VALUES(?,?,?,?)',(title,v.get('kind','Reminder'),v['day'],v.get('notes',''))); db().commit(); return jsonify(id=cur.lastrowid)

@app.delete('/api/events/<int:id>')
def delete_event(id): db().execute('DELETE FROM events WHERE id=?',(id,)); db().commit(); return jsonify(ok=True)

@app.get('/api/export')
def export():
    import csv, io
    out=io.StringIO(); w=csv.writer(out); w.writerow(['Title','Subject','Category','Priority','Due date','Hours','Status'])
    for t in rows('SELECT t.*,s.name subject FROM tasks t LEFT JOIN subjects s ON s.id=t.subject_id'):w.writerow([t['title'],t['subject'],t['category'],t['priority'],t['due_date'],t['duration'],'Completed' if t['done'] else 'Pending'])
    from flask import Response
    return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=studyflow-tasks.csv'})

init_db()
if __name__=='__main__': app.run(debug=True, port=5000)
