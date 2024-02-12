import json

import logging
import os
import tempfile
import zipfile
from datetime import datetime

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)


def create_zip(tag, files_temp_dir, zip_temp_dir):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    zip_file_name = f"{tag}_{timestamp}.zip"
    zip_path = os.path.join(zip_temp_dir, zip_file_name)
    # Open a new ZIP file in write mode
    with zipfile.ZipFile(zip_path, 'a', zipfile.ZIP_DEFLATED) as zipf:
        # Iterate through all files in the folder
        for file in os.listdir(files_temp_dir):
            # Get the full path of the file
            file_path = os.path.join(files_temp_dir, file)
            # Add the file to the ZIP file using its own file name
            zipf.write(file_path, file)
    return zip_path


def upload_file(zip_path, bucket, object_name=None):
    """Upload a file to an S3 bucket

    :param zip_path: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = os.path.basename(zip_path)

    # Upload the file
    s3_client = boto3.client('s3')
    try:
        s3_client.upload_file(zip_path, bucket, object_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True


def download_file(bucket_name, object_name, files_temp_dir):
    s3 = boto3.client('s3')
    file_path = os.path.join(files_temp_dir, object_name)
    try:
        with open(file_path, 'wb') as f:
            s3.download_fileobj(bucket_name, object_name, f)
    except ClientError as e:
        logging.error(e)
        return None
    return 0


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

    tag = event['pathParameters']['tag']

    logging.info(f"Tag is {tag}")

    dynamo_db = boto3.resource('dynamodb')

    try:
        table = dynamo_db.Table('project-lambda-api-files-lookup')
        response = table.query(
            IndexName='tag-index',
            KeyConditionExpression=Key('tag').eq(tag)
        )
    except Exception as e:
        logging.error(e)
        return {
            "statusCode": 502,
            "body": json.dumps({
                "message": "An error occurred while retrieving items from Amazon DynamoDB",
            }),
        }

    items = response['Items']

    with tempfile.TemporaryDirectory() as files_temp_dir, tempfile.TemporaryDirectory() as zip_temp_dir:
        try:
            logging.info(f"Files temp dir: {files_temp_dir}")
            logging.info(f"Zip temp dir: {zip_temp_dir}")
            for item in items:
                logging.info(f"Found item: {item}")
                uri = item.get('uri')
                logging.info(f"Uri is: {uri}")
                download_file('project-lambda-api-files', uri, files_temp_dir)
                logging.info(f"Correctly downloaded file {uri}")
            zip_path = create_zip(tag, files_temp_dir, zip_temp_dir)
            object_name = os.path.basename(zip_path)
            logging.info(f"Correctly created zip file {object_name}")
            upload_file(zip_path, 'project-lambda-api-files')
            logging.info(f"Correctly uploaded zip file {object_name} to Amazon S3")
            signed_url = create_presigned_url('project-lambda-api-files', object_name)
        except Exception as e:
            logging.error(e)
            return {
                "statusCode": 502,
                "body": json.dumps({
                    "message": "An error occurred while working with Amazon S3",
                }),
            }

    if signed_url is None:
        return {
            "statusCode": 502,
            "body": json.dumps({
                "message": "Error getting signed url",
            }),
        }

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": signed_url,
        }),
    }
