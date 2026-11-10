# StudyFlow

A responsive personal study planner built with Flask, SQLite, HTML, CSS and JavaScript. Tasks, subjects, study sessions, calendar events and completed Pomodoro sessions persist in a local SQLite database.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). The database is created at `database/studyflow.db` on first run with a small set of example subjects, tasks and sessions. Delete that file to start with an empty database; the starter records will be seeded again automatically.

## Features

- Dashboard with live task counts, completed study time, weekly activity and upcoming deadlines.
- Task creation, editing, deletion, completion, search, filters and CSV export.
- Subjects with color, description, task counts and completed study time.
- Daily and weekly study schedule with overlap validation, completion tracking and deletion.
- Monthly calendar that combines sessions, task deadlines and user created reminders.
- Focus, short break and long break timer; completed focus blocks are recorded in SQLite.
- Progress charts based on completed sessions and subject records.
- Responsive sidebar, mobile layout and a persistent dark appearance preference.

Charts use Chart.js from jsDelivr, and the interface loads DM Sans and Manrope from Google Fonts. An internet connection is needed for those visual assets; core Flask data features are local.
