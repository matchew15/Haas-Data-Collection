import json
import os
import psycopg2 as pg
import paho.mqtt.client as mqtt
import pandas as pd
import time
from datetime import datetime


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.connected_flag = True
        client.publish('FWH2200_PG_DB/status', 'Publisher: 1', retain=True)
    else:
        client.bad_connection_flag = True


_cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'historian.config')
with open(_cfg) as config:
    mqttBroker = config.readline().split(" = ")[1].strip()
    hostname   = config.readline().split(" = ")[1].strip()
    _           = config.readline()  # group ID (unused)
    db         = config.readline().split(" = ")[1].strip()
    user       = config.readline().split(" = ")[1].strip()
    password   = config.readline().split(" = ")[1].strip()

conn = pg.connect(f"dbname={db} user={user} password={password} host={hostname}")

try:
    cur = conn.cursor()
    print("Publisher DB connection established")
except (Exception, pg.DatabaseError) as error:
    print(error)

port = 1883
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "FWH2200_PG_DB")
client.will_set("FWH2200_PG_DB/status", "Publisher: 0", retain=True)
client.on_connect = on_connect
client.loop_start()
client.connect(mqttBroker, port)

topic_list = ['VF-2_1', 'VF-2_2']

while True:
    dataObj = {}
    try:
        for topic in topic_list:
            CMD = f'SELECT * FROM "AML"."{topic}" ORDER BY "timestamp" DESC LIMIT 1'
            df = pd.read_sql_query(CMD, conn)
            dataObj[topic] = df.to_dict(orient='records')

        message = json.dumps(dataObj)
        client.publish('FWH2200_PG_DB/output', message, qos=1)
        print(f"Message sent at {datetime.now().strftime('%H:%M:%S')}")
        time.sleep(1)
    except Exception as e:
        print(f'Publisher error: {e}')
