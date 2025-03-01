import os
import logging
import time
import io

import boto3
import requests
from gtfs_realtime_pb2 import FeedMessage

GTFS_VEHICLE_POSITION_URL = os.environ.get('GTFS_VEHICLE_POSITION_URL')
INGESTED_DATA_S3_BUCKET = os.environ.get('INGESTED_DATA_S3_BUCKET')
INGESTED_DATA_S3_PREFIX = os.environ.get('INGESTED_DATA_S3_PREFIX')
API_KEY_PARAMETER_ARN = os.environ.get('API_KEY_PARAMETER_ARN')

class EntityField:
    def __init__(self, name, getter_fn):
        self.name = name
        self.getter_fn = getter_fn

    def get_string_value(self, entity):
        try:
            return str(self.getter_fn(entity))
        except AttributeError:
            return 'None'


ENTITY_FIELDS = [
    EntityField('timestamp', lambda e: e.vehicle.timestamp),
    EntityField('trip_id', lambda e: e.vehicle.trip.trip_id),
    EntityField('trip_start_time', lambda e: e.vehicle.trip.start_time),
    EntityField('trip_start_date', lambda e: e.vehicle.trip.start_date),
    EntityField('route_id', lambda e: e.vehicle.trip.route_id),
    EntityField('direction_id', lambda e: e.vehicle.trip.direction_id),
    EntityField('latitude', lambda e: e.vehicle.position.latitude),
    EntityField('longitude', lambda e: e.vehicle.position.longitude),
    EntityField('bearing', lambda e: e.vehicle.position.bearing),
    EntityField('current_stop_sequence', lambda e: e.vehicle.current_stop_sequence),
    EntityField('current_status', lambda e: e.vehicle.current_status),
    EntityField('stop_id', lambda e: e.vehicle.stop_id),
    EntityField('occupancy_status', lambda e: e.vehicle.occupancy_status)
]

ssm_client = boto3.client('ssm')
s3 = boto3.resource('s3')

logger = logging.getLogger()
logger.setLevel("INFO")

def lambda_handler(event, context):
    logger.info(f"event: {event}")
    logger.info(f"context: {context}")
    try:
        r = ssm_client.get_parameter(Name=API_KEY_PARAMETER_ARN)
        parameter = r['Parameter']
        api_key = parameter['Value']

        record_count = 0 
        request_headers = {
            'Cache-Control': 'no-cache',
            'api_key': api_key
        }
        r = requests.get(GTFS_VEHICLE_POSITION_URL, headers=request_headers)
        if r.status_code == requests.codes.ok:

            message = FeedMessage()
            message.ParseFromString(r.content)
            logger.info(f"GTFS message timestamp {message.header.timestamp} with {len(message.entity)} entities")
            record_count = len(message.entity)

            csv_buffer = io.StringIO()
            header_row = ','.join([entity_field.name for entity_field in ENTITY_FIELDS]) + "\n"
            csv_buffer.write(header_row)
            for entity in message.entity:
                record_row = ','.join([entity_field.get_string_value(entity) for entity_field in ENTITY_FIELDS]) + "\n"
                csv_buffer.write(record_row)

            t = time.gmtime(message.header.timestamp)
            s3_object_key = f"{INGESTED_DATA_S3_PREFIX}{t.tm_year:04}-{t.tm_mon:02}-{t.tm_mday:02}/{t.tm_hour:02}:{t.tm_min:02}:{t.tm_sec:02}-{message.header.timestamp}.csv"
            logger.info(f"Writing {len(csv_buffer.getvalue())} bytes to s3://{INGESTED_DATA_S3_BUCKET}/{s3_object_key}")
            s3_object = s3.Object(INGESTED_DATA_S3_BUCKET, s3_object_key)
            s3_object.put(Body=csv_buffer.getvalue())

        else:
            logger.error(f"Received {r.status_code}: {r.text}")

        return {
            "statusCode": 200,
            "message": f"Processed {record_count} records"
        }
    except Exception as e:
        logger.error(f"Error {str(e)}")
        raise


