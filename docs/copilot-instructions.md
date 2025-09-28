# Copilot Instructions for futsal_app

## Project Overview
- **futsal_app** is a Django-based web application for managing futsal games, players, and attendance.
- Core domains: `games` (game scheduling, player slots, booking history), `member` (player registration, admin management), and `players` (player data, migrations).
- Data flows: Players sign up, admins manage games/players, attendance is tracked, and booking history is recorded for fair slot assignment.

## Key Components & Structure
- `futsal_app/`: Django project settings, URLs, and WSGI/ASGI entrypoints.
- `games/`: Models for Game, Player, BookingHistory; views for game management; templates for game-related UI.
- `member/`: Handles player registration, admin features, and member templates.
- `players/`: (Legacy or auxiliary) player-related logic and migrations.
- `static/` and `templates/`: Static assets and HTML templates, organized by app.

## Developer Workflows
- **Install dependencies:** `pip install -r requirements.txt`
- **Run server:** `python manage.py runserver`
- **Run migrations:** `python manage.py makemigrations && python manage.py migrate`
- **Create superuser:** `python manage.py createsuperuser`
- **Run tests:** `python manage.py test`
- **Docker:** Use `docker-compose.yaml` and `Dockerfile` for containerized workflows.

## Project-Specific Patterns
- **Player attendance:** Managed via checkboxes in the UI; changes are logged in `BookingHistory` for audit and slot assignment.
- **Game slots:** Players are divided into permanent and reserved slots per game; logic in `games/models.py` and `games/views.py`.
- **Admin management:** Only superusers can add/edit players and games.
- **Email notifications:** (If implemented) likely handled in `games/views.py` or via Django signals.
- **Templates:** Use app-specific subfolders in `templates/` (e.g., `templates/games/`, `templates/members/`).

## Conventions & Integration
- **App structure:** Follows Django best practices for apps, migrations, and templates.
- **No custom management commands** (unless added later).
- **Database:** Uses SQLite by default (`db.sqlite3`).
- **Static files:** Place in `static/` and reference in templates.
- **External dependencies:** See `requirements.txt` for all Python packages.

## Examples
- To add a new model, update the relevant `models.py`, run migrations, and register in `admin.py`.
- To customize player registration, edit `member/forms.py` and `member/views.py`.
- For new game logic, see `games/views.py` and `games/models.py`.

---

For more details, see `README.md` and app-level docstrings. When in doubt, follow Django conventions unless project files indicate otherwise.
