# our_project — quick start

This repository is a small Django scaffold. These notes show how to run it on Windows PowerShell from the repository root.

1) Recommended (use the bundled venv python when possible):

```powershell
# Use the venv python directly (no activation required)
.\Scripts\python.exe .\our_project\manage.py runserver

# Or run tests
.\Scripts\python.exe .\our_project\manage.py test
```

2) Activate the venv (optional):

```powershell
# Allow scripts for this session and activate the venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\Scripts\Activate.ps1
python .\our_project\manage.py runserver
```

3) If you prefer running `python manage.py` from the repo root, `manage.py` has been added at the repository root and mirrors the inner manage.py.

Notes
- The app `my_app` is scaffolded but not yet added to `INSTALLED_APPS` in `our_project/our_project/settings.py` — add it before creating migrations.
- The project uses SQLite at `our_project/db.sqlite3` for development.