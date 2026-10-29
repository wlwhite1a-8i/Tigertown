# TigerTown setup

See [README.md](README.md) for the public source setup. The survey-derived database seed, researched catalog snapshot, and original uploaded project archive are pending approval for public sharing. Use `database/schema.sql` to inspect or initialize the 17-table MySQL structure.

## Backend dependencies

Create `.venv` with Python 3.10+ and install `requirements.txt`. Run `python server/setup.py` to configure a private `.env`, then run `python server/server.py` and open `http://127.0.0.1:5000`.

For production use a WSGI server and HTTPS. A documented starting command is `waitress-serve --host=127.0.0.1 --port=5000 --call server.server:create_app`.

For tests install `requirements-dev.txt`, then run `python -m pytest tests -q`. Tests use a SQLite adapter.
