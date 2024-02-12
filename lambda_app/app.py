import json

import logging
import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)


def create_presigned_url(bucket_name, object_name, expiration=3600):
    """Generate a presigned URL to share an S3 object

    :param bucket_name: string
    :param object_name: string
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """

    # Generate a presigned URL for the S3 object
    s3_client = boto3.client('s3')
    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name,
                                                            'Key': object_name},
                                                    ExpiresIn=expiration)
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL
    return response


def lambda_handler(event, context):
    """

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format

        Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

    context: object, required
        Lambda Context runtime methods and attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    ------
    API Gateway Lambda Proxy Output Format: dict

        Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """

    logging.info("Start calling Lambda Function")

    file_id = event['pathParameters']['id']

    logging.info(f"file id is {file_id}")

    dynamo_db = boto3.resource('dynamodb')
    try:
        table = dynamo_db.Table('project-lambda-api-files-lookup')
        response = table.get_item(
            Key={
                'id': file_id
            }
        )
    except Exception as e:
        logging.error(e)
        return {
            "statusCode": 400,
            "body": json.dumps({
                "message": "An error occurred while retrieving items from Amazon DynamoDB",
            }),
        }

    item = response['Item']

    logging.info(f"Item is {item}")

    uri = item.get('uri')
    signed_url = create_presigned_url('project-lambda-api-files', uri)

    if signed_url is None:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "message": "An error occurred while retrieving data from Amazon S3",
            }),
        }

    logging.info(f"Signed url is {signed_url}")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": signed_url,
        }),
    }
