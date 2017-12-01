# proj-MeetMe

A meeting arranger. Getting busy time period from people and outputing common free time(s).

## What you need

Google calendar api credentials json, a functional MongoDB.

## Usage

- Import your Google calendar api credentials json into /meetings
- Copy its file's name(usually "client_id.json") and paste into app.ini's "GOOGLE_KEY_FILE" option.
- Modify app.ini's MongoDB perimeters.
- You can assign another port number by modifying it in the app.ini
- "make start"
-  Set date range and time range, and then you can see your free and busy times.
