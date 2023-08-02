from flask import Flask
from flask import request
from threading import Thread
import time
import requests
from datetime import datetime, timedelta

now = datetime.now() + timedelta(hours=6)
dt_string = now.strftime("%d/%m/%Y %H:%M:%S")

app = Flask('')


@app.route('/')
def home():
  return f"I'm alive {dt_string}"


def run():
  app.run(host='0.0.0.0', port=80)


def keep_alive():
  t = Thread(target=run)
  t.start()
