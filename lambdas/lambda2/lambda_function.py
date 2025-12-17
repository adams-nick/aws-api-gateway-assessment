import json

def lambda_handler(event, context):
  print('Lambda 2 - python - invoked with event: ', event)

  return {
    'statusCode': 200,
    'body': json.dumps({'message': 'Lambda 2 python success'})
  }