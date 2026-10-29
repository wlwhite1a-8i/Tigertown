# TigerTown: Explore Jackson, Mississippi

A Jackson State University course project by **404 Founders**: Markail Lewis, Walter White, Zalan Barrett, and Jcori Hargon.

TigerTown helps students browse researched places in Jackson and surrounding cities. It uses an HTML/CSS/JavaScript frontend, Python Flask backend, and MySQL database.

## Start here

Follow [START_HERE.md](START_HERE.md) to open the project in Visual Studio Code, import the SQL database, configure the server, and run the website.

## Project files

- [HTML frontend](frontend/index.html)
- [CSS design](frontend/style.css)
- [JavaScript interactions](frontend/main.js)
- [Python Flask backend](server/server.py)
- [Database setup](database/TigerTown_Jackson_Places.sql)
- [Researched place data](database/TigerTown_Place_Research_Update.sql)
- [Backend tests](tests/test_server.py)

Catalog updates occur after an administrator saves a place or explicitly selects Refresh catalog. There are no background catalog checks. Browser favorites stay local to the browser.

## Implementation status

The static frontend preview uses `frontend/catalog.json`. Run the complete Python project with your MySQL server for administrator database editing. Native MySQL integration and capacity testing still need verification on the team's server. Backend regression tests use a SQLite adapter and do not replace native MySQL tests.

Use `python server/setup.py` to configure credentials privately. The `.env` file is excluded from version control. Only the blank `.env.example` template is included.

The SQL scripts contain anonymous survey research and source citations. Refer to the included setup guide for data provenance, geographic outline attribution, and deployment instructions.
