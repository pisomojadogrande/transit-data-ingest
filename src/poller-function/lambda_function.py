import os
import logging
import boto3

import requests
import gtfs_realtime_pb2

GTFS_VEHICLE_POSITION_URL = os.environ.get('GTFS_VEHICLE_POSITION_URL')
API_KEY_PARAMETER_ARN = os.environ.get('API_KEY_PARAMETER_ARN')

ssm_client = boto3.client('ssm')

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
            logger.info(f"GTFS response length {len(r.content)}")

            message = FeedMessage()
            message.ParseFromString(r.content)
            logger.info(f"GTFS message timestamp {message.header.timestamp} with {len(message.entity)} entities")
            record_count = len(message.entity)

        else:
            logger.error(f"Received {r.status_code}: {r.text}")

        return {
            "statusCode": 200,
            "message": f"Processed {record_count} records"
        }
    except Exception as e:
        logger.error(f"Error {str(e)}")
        raise


