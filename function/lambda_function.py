import json
import logging
import boto3
import requests  # Import the requests module for making HTTP requests

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def download_file(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading file: {e}")
        return None


# def parseBody(event):
#     if 'body' in event:
#         body = json.loads(event['body'])
#         logger.info(f"body is {body}")
#         if 'img_id' in body:
#             img_id = body['img_id']
#             logger.info(f"img_id is {img_id}")
#             return img_id
#         else:
#             return None


def lambda_handler(event, context):
    img_id = event.get
    if img_id is None:
        return {
            'statusCode': 400,
            'body': json.dumps('Invalid body')
        }

    dynamo_db = boto3.resource('dynamodb')
    table = dynamo_db.Table('Images')

    logger.info("Start reading from DynamoDB")

    try:
        response = table.get_item(
            Key={
                'img_id': img_id
            }
        )
        item = response.get('Item')
        logger.info(f"Retrieved item: {item}")

        if item:
            url = item.get('url')
            logger.info(f"URL: {url}")

            # Download the file from the URL
            content = download_file(url)

            if content:
                return {
                    'statusCode': 200,
                    'body': content,
                    'headers': {
                        'Content-Type': 'application/octet-stream',
                        'Content-Disposition': 'attachment; filename="image.png"'
                    }
                }
            else:
                return {
                    'statusCode': 500,
                    'body': json.dumps('Error downloading file')
                }
        else:
            return {
                'statusCode': 404,
                'body': json.dumps('Item not found')
            }
    except Exception as e:
        logger.error(f"Error accessing DynamoDB: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps('Error accessing DynamoDB')
        }
