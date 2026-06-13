import os
import json
import paho.mqtt.client as mqtt


_cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'historian.config')
with open(_cfg) as config:
    mqttBroker = config.readline().split(" = ")[1].strip()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected, rc =", rc)
    else:
        print("Bad connection, rc =", rc)


def on_message(client, userdata, message):
    msg = message.payload.decode("utf-8")
    print("Received on", message.topic)
    try:
        print(json.dumps(json.loads(msg), indent=2))
    except Exception:
        print(msg)


port = 1883
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "dash_subscriber")
client.connect(mqttBroker, port)
client.on_connect = on_connect
client.on_message = on_message

client.subscribe('FWH2200_PG_DB/#')
client.loop_forever()
