import json
import paho.mqtt.client as mqtt
from flask import Flask, request, jsonify
import threading
from datetime import datetime
import os

# --- CONFIGURACION GENERAL (Render usa env vars) ---
MQTT_BROKER = os.environ.get("MQTT_BROKER")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 8883))
MQTT_USER = os.environ.get("MQTT_USER")
MQTT_PASS = os.environ.get("MQTT_PASS")
TOKEN_INTERNO = os.environ.get("TOKEN_INTERNO", "secreto123")

# --- LOGS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "logs_central.txt")

with open(LOG_FILE, "a", encoding="utf-8") as f:
    f.write("=== Inicio de logs Servidor Central RORI ===\n")
print(f"# Archivo de logs central: {LOG_FILE}")

def guardar_log(topico, mensaje):
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linea = f"[{ts}] [{topico}] {mensaje}\n"
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(linea)
    except Exception as e:
        print(f"# Error guardando log: {e}")

# --- MQTT ---
def on_connect(client, userdata, flags, rc):
    print(f"# Conectado al broker central: {rc}")
    # Suscripción global a logs y status de todos los relés
    client.subscribe("rori/+/rele/+/status")
    client.subscribe("rori/+/rele/+/log")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        topic_parts = msg.topic.split("/")

        if "status" in topic_parts:
            print(f"[STATUS] {msg.topic} -> {payload}")
            guardar_log("status", payload)

        elif "log" in topic_parts:
            print(f"[LOG] {msg.topic} -> {payload}")
            guardar_log("log", payload)

    except Exception as e:
        print(f"# Error al procesar mensaje: {e}")

client = mqtt.Client()
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.tls_set()
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

# --- FLASK API ---
app = Flask(__name__)

@app.route("/enviar-comando", methods=["POST"])
def enviar_comando():
    try:
        data = request.json
        estancia = data.get("estancia_uuid")
        device = data.get("device_uuid")
        accion = data.get("accion")

        if not estancia or not device or not accion:
            return jsonify({"ok": False, "error": "Faltan parametros"}), 400

        if accion not in {"abrir", "abrir_temporal", "cerrar"}:
            return jsonify({"ok": False, "error": "Accion no valida"}), 400

        comando = json.dumps({"comando": accion, "token": TOKEN_INTERNO})
        topic = f"rori/{estancia}/rele/{device}/control"
        client.publish(topic, comando)

        print(f"# Comando HTTP recibido -> MQTT {accion} para {device} en {estancia}")
        guardar_log("comando_http", f"{accion} -> {device} en {estancia}")
        return jsonify({"ok": True, "mensaje": f"Comando {accion} enviado"}), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

def run_flask():
    port = int(os.environ.get("PORT", 7000))  # Render asigna el puerto en PORT
    app.run(host="0.0.0.0", port=port)

# --- Iniciar Flask y MQTT ---
flask_thread = threading.Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

client.loop_forever()
