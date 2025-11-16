from flask import Flask, Response
from clean_calendar import clean_calendar

app = Flask(__name__)

@app.route('/')
def serve_calendar():
    cleaned_ical = clean_calendar()
    return Response(cleaned_ical, mimetype='text/calendar')

if __name__ == '__main__':
    app.run()
