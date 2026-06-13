import os
from flask import Flask, jsonify, request
from flask_restful import Api, Resource
import psycopg2 as pg
import pandas as pd


_cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'historian.config')
with open(_cfg) as config:
    _            = config.readline()   # MQTT Broker IP (unused by REST)
    hostname     = config.readline().split(" = ")[1].strip()
    __           = config.readline()   # group ID (unused)
    db           = config.readline().split(" = ")[1].strip()
    user         = config.readline().split(" = ")[1].strip()
    password     = config.readline().split(" = ")[1].strip()

try:
    conn = pg.connect(f"dbname={db} user={user} password={password} host={hostname}")
    cur = conn.cursor()
    print("REST server DB connection established")
except (Exception, pg.DatabaseError) as error:
    print(error)

app = Flask(__name__)
api = Api(app)

_SCHEMA = '"AML"'


class Welcome(Resource):
    def get(self):
        return "Haas CNC REST API — GET /all for available endpoints"


class All(Resource):
    def get(self):
        return {
            "Machine list":       "/machinelist",
            "Last 10 records":    "/last10?codename=<table>",
            "XYZ coordinates":    "/XYZ?codename=<table>",
        }


class Machines(Resource):
    def get(self):
        try:
            cur.execute(f'SELECT * FROM {_SCHEMA}."CNC"')
            rows = cur.fetchall()
            data = {
                i: {desc.name: row[j] for j, desc in enumerate(cur.description)}
                for i, row in enumerate(rows)
            }
            return data
        except (Exception, pg.DatabaseError) as error:
            print(error)
            return {"error": str(error)}, 500


class MachineDataLast(Resource):
    def get(self):
        codename = request.args.get("codename")
        if not codename:
            return {"error": "codename parameter required"}, 400
        try:
            df = pd.read_sql_query(
                f'SELECT * FROM {_SCHEMA}."{codename}" ORDER BY "timestamp" DESC LIMIT 10',
                conn,
            )
            return df.to_json()
        except (Exception, pg.DatabaseError) as error:
            print(error)
            return {"error": "Query failed"}, 500


class Coordinates(Resource):
    def get(self):
        codename = request.args.get("codename")
        if not codename:
            return {"error": "codename parameter required"}, 400
        coord = 'Present machine coordinate position '
        try:
            cur.execute(
                f'SELECT "{coord}X", "{coord}Y", "{coord}Z" '
                f'FROM {_SCHEMA}."{codename}" ORDER BY "timestamp" DESC LIMIT 1'
            )
            row = cur.fetchone()
            if row is None:
                return {"error": "No data found"}, 404
            return {"X": float(row[0]), "Y": float(row[1]), "Z": float(row[2])}
        except (Exception, pg.DatabaseError) as error:
            print(error)
            return {"error": "Query failed"}, 500


api.add_resource(Welcome, '/')
api.add_resource(All, '/all')
api.add_resource(Machines, '/machinelist')
api.add_resource(MachineDataLast, '/last10')
api.add_resource(Coordinates, '/XYZ')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=False)
