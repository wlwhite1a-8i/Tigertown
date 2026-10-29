# TigerTown: Explore Jackson, Mississippi

A Jackson State University course project by **404 Founders**: Markail Lewis, Walter White, Zalan Barrett, and Jcori Hargon.

## Source code

- [HTML](frontend/index.html)
- [CSS](frontend/style.css)
- [JavaScript](frontend/main.js)
- [Python Flask backend](server/server.py)
- [Private setup helper](server/setup.py)
- [MySQL schema: 17 tables](database/schema.sql)
- [Backend tests](tests/test_server.py)

## Data availability

This public source version includes an empty catalog and database structure. Survey response data, the uploaded SQLite SQL attachment, and the uploaded full-project ZIP are pending approval for public sharing and are not published as repository files.

## Run in Visual Studio Code

1. Open `TigerTown.code-workspace`.
2. Create a Python virtual environment and install `requirements.txt`.
3. Import `database/schema.sql` into a fresh MySQL 8.0.16+ database.
4. Run `python server/setup.py` to configure your database connection and administrator password privately.
5. Run `python server/server.py` and open `http://127.0.0.1:5000`.

The schema starts empty. The data-free frontend snapshot starts with no places or categories. Import approved research records separately to reproduce the original researched catalog.

Admin saves and the explicit Refresh catalog button control data refreshes. No polling runs in the frontend. Favorites remain in browser storage.

MySQL credentials and the administrator password hash are stored in the excluded `.env` file. `.env.example` is a blank configuration template.

## Verification status

Backend tests use a SQLite adapter. They do not replace native MySQL integration, load, storage, or backup/restore tests on the team's host.
