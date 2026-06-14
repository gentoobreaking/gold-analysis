"""
InfluxDB client wrapper for market data
"""
from influxdb_client import InfluxDBClient, Point, WriteOptions
from influxdb_client.client.write_api import SYNCHRONOUS
from .config import settings, get_influx_client, init_influxdb


def get_write_api(client: InfluxDBClient):
    """Return a write API with default options"""
    return client.write_api(write_options=SYNCHRONOUS)


def get_query_api(client: InfluxDBClient):
    """Return a query API"""
    return client.query_api()


def write_measurement(measurement: str, tags: dict, fields: dict, timestamp=None):
    """Utility to write a single measurement"""
    client = get_influx_client()
    point = Point(measurement)
    for k, v in tags.items():
        point = point.tag(k, v)
    for k, v in fields.items():
        point = point.field(k, v)
    if timestamp:
        point = point.time(timestamp)
    write_api = get_write_api(client)
    write_api.write(bucket=settings.influxdb_bucket, record=point)


def query_measurement(flux: str):
    """Execute a Flux query and return raw table result"""
    client = get_influx_client()
    query_api = get_query_api(client)
    return query_api.query(flux)
