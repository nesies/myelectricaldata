import locale
import logging
import time
import typing as t
from os import getenv, environ, path

import yaml

from config import LOG_FORMAT, LOG_FORMAT_DATE
from dependencies import APPLICATION_PATH_DATA, str2bool
from models.config import Config
from models.database import Database
from models.influxdb import InfluxDB
from models.mqtt import Mqtt

# LOGGING CONFIGURATION
if path.exists("/data/config.yaml"):
    with open(f'/data/config.yaml') as file:
        config = yaml.load(file, Loader=yaml.FullLoader)

if "DEBUG" in environ and str2bool(getenv("DEBUG")):
    logging_level = logging.DEBUG
else:
    logging_level = logging.INFO

if "log2file" in config and config["log2file"]:
    logging.basicConfig(
        filename=f"/log/myelectricaldata.log",
        format=LOG_FORMAT,
        datefmt=LOG_FORMAT_DATE,
        level=logging_level
    )
    console = logging.StreamHandler()
    console.setLevel(logging_level)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_FORMAT_DATE)
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)
else:
    logging.basicConfig(
        format=LOG_FORMAT,
        datefmt=LOG_FORMAT_DATE,
        level=logging_level
    )


class EndpointFilter(logging.Filter):
    def __init__(
            self,
            path: str,
            *args: t.Any,
            **kwargs: t.Any,
    ):
        super().__init__(*args, **kwargs)
        self._path = path

    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find(self._path) == -1


uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.addFilter(EndpointFilter(path="/import_status"))

locale.setlocale(locale.LC_ALL, 'fr_FR.UTF-8')

CONFIG = Config(
    path=APPLICATION_PATH_DATA
)
CONFIG.load()
CONFIG.display()
CONFIG.check()

DB = Database(CONFIG)
DB.init_database()
DB.unlock()

CONFIG.set_db(DB)

INFLUXDB_CONFIG = CONFIG.influxdb_config()
INFLUXB_ENABLE = False
INFLUXDB = None

if "method" in INFLUXDB_CONFIG:
    method = INFLUXDB_CONFIG["method"]
else:
    method = "SYNCHRONOUS"

write_options = []
if "batching_options" in INFLUXDB_CONFIG:
    write_options = INFLUXDB_CONFIG["batching_options"]

if INFLUXDB_CONFIG and "enable" in INFLUXDB_CONFIG and INFLUXDB_CONFIG["enable"]:
    INFLUXB_ENABLE = True
    INFLUXDB = InfluxDB(
        hostname=INFLUXDB_CONFIG["hostname"],
        port=INFLUXDB_CONFIG["port"],
        token=INFLUXDB_CONFIG["token"],
        org=INFLUXDB_CONFIG["org"],
        bucket=INFLUXDB_CONFIG["bucket"],
        method=method,
        write_options=write_options
    )
    if CONFIG.get("wipe_influxdb"):
        INFLUXDB.purge_influxdb()
        CONFIG.set("wipe_influxdb", False)
        time.sleep(1)

MQTT_CONFIG = CONFIG.mqtt_config()
if MQTT_CONFIG and "enable" in MQTT_CONFIG and MQTT_CONFIG["enable"]:
    MQTT = Mqtt(
        hostname=MQTT_CONFIG["hostname"],
        port=MQTT_CONFIG["port"],
        username=MQTT_CONFIG["username"],
        password=MQTT_CONFIG["password"],
        client_id=MQTT_CONFIG["client_id"],
        prefix=MQTT_CONFIG["prefix"],
        retain=MQTT_CONFIG["retain"],
        qos=MQTT_CONFIG["qos"]
    )
