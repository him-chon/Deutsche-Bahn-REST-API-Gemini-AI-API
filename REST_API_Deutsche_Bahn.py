
"""
Getting Started

1. This program requires the following packages to be installed.

   pip install python-dotenv==1.0.1
   pip install google-generativeai==0.4.1
   pip install flask==3.0.2
   pip install flask_restx==1.3.0
   pip install requests==2.31.0

   Alternatively, you can use requirement.txt by
   pip install -r requirements.txt

2. Create a file called `.env` in the same directory as this file.  This file
   will contain the Google API key you generatea in the next step.

3. Go to the following page, click on the link to "Get an API key", and follow
   the instructions to generate an API key:

   https://ai.google.dev/tutorials/python_quickstart

4. Add the following line to your `.env` file, replacing `your-api-key` with
   the API key you generated, and save the file:

   GOOGLE_API_KEY=your-api-key
"""


import os
from pathlib import Path
from dotenv import load_dotenv          # Needed to load the environment variables from the .env file
import google.generativeai as genai     # Needed to access the Generative AI API
import requests
from flask import Flask, request, send_file
from flask_restx import Resource, Api
from flask_restx import fields
from flask_restx import reqparse
import sqlite3
from datetime import datetime



db_file   = "database.db"           # Use this variable when referencing the SQLite database file.
txt_file  = "tourism_guide.txt"          # Use this variable when referencing the txt file output for gemini api.


# Load the environment variables from the .env file
load_dotenv()

# Configure the API key
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

# Create a Gemini Pro model
gemini = genai.GenerativeModel('gemini-pro')

app = Flask(__name__)
api = Api(app,
          default="Stops Operations",  # Default namespace
          title="Smart API for the Deutsche Bahn",  # Documentation Title
          description="Extension of v6.db.transport.rest REST API for tourism guide generation")  # Documentation Description

# Model for updating a stop
stop_model = api.model('Stop', {
    'name': fields.String(required=False, description='Name of the stop', example='Morty’s House'),
    'latitude': fields.Float(required=False, description='Latitude of the stop', min=-90, max=90, example=-33.918859),
    'longitude': fields.Float(required=False, description='Longitude of the stop', min=-180, max=180, example=151.231034),
    'last_updated': fields.String(required=False, description='Last updated time in yyyy-mm-dd-hh:mm:ss format', example='2024-03-09-12:00:40'),
    'next_departure': fields.String(required=False, description='Next departure information', example='Platform 4 A-C towards Sollstedt')
})

# Define parser for the 'query' parameter
query_parser = reqparse.RequestParser()
query_parser.add_argument('query', type=str, required=True, location='args', help='Query to search for stops')

# Define parser for the 'include' parameter
include_parser = reqparse.RequestParser()
include_parser.add_argument('include', type=str, required=False, location='args', help='Fields to be included in stop information')

# Initialize database
# Create the database file if it does not exist
conn = sqlite3.connect(db_file, check_same_thread=False)
c = conn.cursor()

# Create the stops table if it doesn't already exist
c.execute(
    '''CREATE TABLE IF NOT EXISTS stops(
        stop_id INTEGER PRIMARY KEY,
        name TEXT,
        latitude REAL,
        longitude REAL,
        last_updated TEXT,
        next_departure TEXT)'''
)
conn.commit()


@api.route('/stops')
class StopsList(Resource):
    @api.response(404, 'No stop matching query found')
    @api.response(400, 'Incorrect parameter')
    @api.response(201, 'New Stops Created')
    @api.response(200, 'Stops Updated')
    @api.response(503, 'API/External API is busy')
    @api.expect(query_parser)
    @api.doc(description="Fetch stops from Deutsche Bahn API and update database")
    def put(self):
        query = query_parser.parse_args()['query']

        if not query:
            api.abort(400, "Query parameter is required.")

        response = requests.get(f'https://v6.db.transport.rest/locations?poi=false&addresses=false&query={query}')

        if response.status_code == 404:
            api.abort(404, "No stop matching query found.")

        if response.status_code == 400 or not response.json():
            api.abort(400, "Incorrect parameter")

        if response.status_code == 503:
            api.abort(503, "External API is busy.")

        # Update database with fetched stops
        if response.status_code == 200:
            stops_data = response.json()
            response_data = []
            c.execute('SELECT * FROM stops')
            n_rows_before = len(c.fetchall())
            for stop in stops_data:
                last_updated = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
                stop_id = stop['id']
                name = stop['name']
                latitude = stop.get('location', {}).get('latitude', 0)  # Default to 0 if not available
                longitude = stop.get('location', {}).get('longitude', 0)  # Default to 0 if not available

                # Insert or replace into the SQLite database
                c.execute(
                    'REPLACE INTO stops (stop_id, name, latitude, longitude, last_updated) VALUES (?, ?, ?, ?, ?)',
                    (stop_id, name, latitude, longitude, last_updated))

                # Generate response
                response_data.append({
                    "stop_id": int(stop_id),
                    "last_updated": last_updated,
                    "_links": {
                        "self": {
                            "href": f"http://{request.host}/stops/{stop_id}"
                        }
                    }
                })
            conn.commit()
            c.execute('SELECT * FROM stops')

            # Check if any new data is created in database
            n_rows_after = len(c.fetchall())
            if n_rows_after > n_rows_before:
                return response_data, 201
            else:
                return response_data, 200


@api.route('/stops/<int:stop_id>')
@api.param('stop_id', 'Stop Identifier')
class Stops(Resource):
    @api.response(404, 'Stop not found or next departure information not available')
    @api.response(400, 'Incorrect parameter')
    @api.response(200, 'Stop information fetched')
    @api.response(503, 'API/External API is busy')
    @api.expect(include_parser)
    @api.doc(description="Fetch stop information by stop ID")
    def get(self, stop_id):
        c.execute('SELECT * FROM stops WHERE stop_id = ?', (stop_id,))
        stop = c.fetchone()

        if stop is None:
            api.abort(404, 'Stop not found')

        direction = None
        platform = None

        # Check for include parameter
        include_fields = include_parser.parse_args()['include']
        if include_fields:
            include_fields = include_fields.split(',')

            # Check for any illegal fields in include parameter
            allowed_fields = ["last_updated", "name", "latitude", "longitude", "next_departure"]

            if any(field not in allowed_fields for field in include_fields):
                api.abort(400,
                          "Include parameter only allow 'last_updated', 'name', 'latitude', 'longitude', and 'next_departure'.")

        # Fetch next departure
        if not include_fields or 'next_departure' in include_fields:
            last_updated = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
            response = requests.get(f'https://v6.db.transport.rest/stops/{stop_id}/departures?duration=120')

            if not response.json() or response.status_code == 400:
                api.abort(400, "Incorrect parameter")

            if response.status_code == 404:
                api.abort(404, "Next departure information not available.")

            if response.status_code == 503:
                api.abort(503, "External API is busy.")

            if response.status_code == 200:
                departure_data = response.json()['departures']
                for departure in departure_data:
                    direction_tmp = departure['direction']
                    platform_tmp = departure['platform']
                    if direction_tmp is not None and platform_tmp is not None:
                        direction = direction_tmp
                        platform = platform_tmp
                        break
                if direction is None and platform is None:
                    api.abort(404, "Next departure information not available.")

                c.execute('UPDATE stops SET last_updated = ?, next_departure = ? WHERE stop_id = ?',
                          (last_updated, f"Platform {platform} towards {direction}", stop_id))
                conn.commit()

        # Construct the response
        response = {
            "stop_id": stop[0],
            "last_updated": stop[4],
            "name": stop[1],
            "latitude": stop[2],
            "longitude": stop[3],
            "next_departure": f"Platform {platform} towards {direction}",
            "_links": {
                "self": {"href": f"http://{request.host}/stops/{stop_id}"}
            }
        }

        # Get next and previous stop_id
        c.execute('SELECT stop_id FROM stops WHERE stop_id > ? ORDER BY stop_id LIMIT 1', (stop_id,))
        next_id = c.fetchone()
        c.execute('SELECT stop_id FROM stops WHERE stop_id < ? ORDER BY stop_id DESC LIMIT 1', (stop_id,))
        prev_id = c.fetchone()

        if next_id is not None:
            response['_links']['next'] = {"href": f"http://{request.host}/stops/{next_id[0]}"}
        if prev_id is not None:
            response['_links']['prev'] = {"href": f"http://{request.host}/stops/{prev_id[0]}"}

        # Filter response according to include parameter
        if include_fields:
            response = {key: value for key, value in response.items() if key in include_fields or key == 'stop_id' or key == '_links'}

        return response, 200

    @api.response(404, 'Stop not found')
    @api.response(400, 'Bad Request')
    @api.response(200, 'Stop deleted successfully')
    @api.doc(description="Delete a stop by Stop ID")
    def delete(self, stop_id):
        # Check if the stop exists
        c.execute('SELECT * FROM stops WHERE stop_id = ?', (stop_id,))
        stop = c.fetchone()

        if stop is None:
            return {"message": f"The stop_id {stop_id} was not found in the database.", "stop_id": stop_id}, 404

        # Proceed with deletion since the stop exists
        c.execute('DELETE FROM stops WHERE stop_id = ?', (stop_id,))
        conn.commit()

        return {"message": f"The stop_id {stop_id} was removed from the database.", "stop_id": stop_id}, 200

    @api.response(404, 'Stop not found')
    @api.response(400, 'Bad Request')
    @api.response(200, 'Stop updated successfully')
    @api.response(503, 'API/External API is busy')
    @api.expect(stop_model)
    @api.doc(description="Update the fields of a stop by stop ID")
    def put(self, stop_id):
        data = request.json

        # Validate input
        if not data:
            api.abort(400, "Request body is required")

        # Check for any illegal fields in the update request
        allowed_fields = ["last_updated", "name", "latitude", "longitude", "next_departure"]

        if any(field not in allowed_fields for field in data.keys()):
            api.abort(400,
                      "Only 'last_updated', 'name', 'latitude', 'longitude', and 'next_departure' fields can be updated.")

        # Check if the stop exists
        c.execute('SELECT * FROM stops WHERE stop_id = ?', (stop_id,))
        stop = c.fetchone()
        if not stop:
            api.abort(404, "Stop not found")

        # Request body validation
        if 'name' in data and not data['name'].strip():
            api.abort(400, "Name cannot be blank")
        if 'last_updated' in data:
            try:
                datetime.strptime(data['last_updated'], "%Y-%m-%d-%H:%M:%S")
            except ValueError:
                api.abort(400, "last_updated must be in yyyy-mm-dd-hh:mm:ss format")
        if 'latitude' in data and (data['latitude'] < -90 or data['latitude'] > 90):
            api.abort(400, "Latitude must be between -90 and 90")
        if 'longitude' in data and (data['longitude'] < -180 or data['longitude'] > 180):
            api.abort(400, "Longitude must be between -180 and 180")
        if 'next_departure' in data and not data['next_departure'].strip():
            api.abort(400, "Next departure cannot be blank")

        # Build the update SQL statement dynamically based on the provided fields
        fields_to_update = ', '.join([f"{key} = ?" for key in data.keys()])
        values_to_update = list(data.values()) + [stop_id]

        # Update last_updated to current time if not provided
        if 'last_updated' not in data:
            data['last_updated'] = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
            fields_to_update += ', last_updated = ?'
            values_to_update.insert(-1, data['last_updated'])

        update_sql = f'UPDATE stops SET {fields_to_update} WHERE stop_id = ?'
        c.execute(update_sql, values_to_update)
        conn.commit()

        # Return the updated stop information
        response = {
            "stop_id": stop_id,
            "last_updated": data['last_updated'],
            "_links": {"self": {"href": f"http://{request.host}/stops/{stop_id}"}}
        }
        return response, 200

@api.route('/operator-profiles/<int:stop_id>')
class OperatorProfiles(Resource):
    @api.response(404, 'Stop not found')
    @api.response(400, 'Bad Request')
    @api.response(200, 'Operator profiles fetched')
    @api.response(503, 'API/External API is busy')
    @api.doc(description="Get profiles for operators operating in a specified stop")
    def get(self, stop_id):
        # Check if the stop_id exists in database
        c.execute('SELECT * FROM stops WHERE stop_id = ?', (stop_id,))
        stop = c.fetchone()

        if not stop:
            api.abort(404, 'Stop not found')

        # External API call to geet departure data within 90 mins
        response = requests.get(f'https://v6.db.transport.rest/stops/{stop_id}/departures?duration=90')

        if not response.json() or response.status_code == 400:
            api.abort(400, "Incorrect parameter")

        if response.status_code == 404:
            api.abort(404, "Operator information not available.")

        if response.status_code == 503:
            api.abort(503, "External API is busy.")

        if response.status_code == 200:
            profiles = []
            i = 0
            unique_operators = set()
            departure_data = response.json()['departures']

            # Build operator profiles using operator name from departure data and generate info using gemini api
            for departure in departure_data:
                operator_name = departure['line']['operator']['name']
                if i >= 5:
                    break
                # Check if operator name is valid and not a duplicate
                if operator_name is None or not operator_name.strip() or operator_name in unique_operators:
                    continue
                # Gemini api call
                question = f'Give me some facts about {operator_name} transport operator in one paragraph'
                info = gemini.generate_content(question).text

                profiles.append(
                    {
                        "operator_name": operator_name,
                        "information": info
                    }
                )
                unique_operators.add(operator_name)
                i += 1

            # Return operator profiles
            response = {
                "stop_id": stop_id,
                "profiles": profiles
            }

            return response, 200

@api.route('/guide')
class Guide(Resource):
    @api.response(400, 'Failed to establish route or not enough stops in database')
    @api.response(200, 'Successfully created and returned tourism guide')
    @api.response(503, 'API/External API is busy')
    @api.doc(description="Create and return tourism guide text file based on stops available in database")
    def get(self):
        c.execute('SELECT stop_id FROM stops')
        rows = c.fetchall()
        stops = [row[0] for row in rows]

        # Check if there are at least 2 stops in database
        if len(stops) < 2:
            api.abort(400, "Not enough stops in database")

        # Permutate different pair of stops to find a journey starting from lowest stop_id pairing with highest stop_id
        stops_asc = stops.copy()
        stops_asc.sort()
        stops_desc = stops.copy()
        stops_desc.sort(reverse=True)
        journey = None

        print(stops_asc)
        print(stops_desc)
        for stop_1 in stops_asc:
            for stop_2 in stops_desc:
                if stop_1 == stop_2:
                    continue
                response = requests.get(f'https://v6.db.transport.rest/journeys?from={stop_1}&to={stop_2}&departure=tomorrow&results=1')
                if response.status_code == 400 or not response.json():
                    api.abort(400, "Incorrect parameter")
                if response.status_code == 503:
                    api.abort(503, "External API is busy.")
                if response.status_code == 200:
                    journey = response.json()['journeys'][0]
                    break
            else:
                continue
            break

        if journey is None:
            api.abort(400, "Failed to establish route based on stops in database")

        # Get all stops in route
        route_list = []
        start = True
        for leg in journey['legs']:
            if start:
                route_list.append(leg['origin']['name'])
                start = False
            route_list.append(leg['destination']['name'])

        route = ', '.join(route_list)

        # Gemini api call
        question = f'Generate a tourism guide for {route} travel route using Germany railway ' \
                   f'using "-" as bullet point. \n' \
                   f'The format is :\n' \
                   f'Tourism Guide for {route} travel route \n' \
                   f'Stop name \n' \
                   f'-Points of Interest: \n' \
                   f'List points of interest and their descriptions \n' \
                   f'-Restaurants: \n' \
                   f'List recommended restaurants and their addresses \n' \
                   f'-Accommodations: \n' \
                   f'List recommended accommodations and their addresses \n' \
                   f'Repeat for other stops \n' \
                   f'Other points of interest along the route (if exists) \n' \
                   f'List other points of interest and their descriptions if exists \n' \
                   f'Transportations \n' \
                   f'List transportation options for visiting points of interest from stations'

        info = gemini.generate_content(question).text

        # Format tourism guide, write to txt file and return
        info = info.replace("*", "")
        info = info.replace("#", "")

        Path(txt_file).write_text(info, encoding='utf-8')

        return send_file(txt_file, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)

