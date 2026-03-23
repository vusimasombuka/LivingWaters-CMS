import boto3
from flask import current_app

def get_s3_client():
    return boto3.client(
        's3',
        aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY'],
        region_name=current_app.config['S3_REGION']
    )

def upload_file_to_s3(file, filename):
    s3 = get_s3_client()
    bucket = current_app.config['S3_BUCKET']
    
    # Upload without ACL (bucket blocks ACLs)
    s3.upload_fileobj(
        file,
        bucket,
        filename,
        ExtraArgs={'ContentType': 'audio/mpeg'}
    )
    
    # Return URL (will be accessible via download route)
    return f"https://{bucket}.s3.{current_app.config['S3_REGION']}.amazonaws.com/{filename}"

def delete_file_from_s3(filename):
    try:
        s3 = get_s3_client()
        bucket = current_app.config['S3_BUCKET']
        s3.delete_object(Bucket=bucket, Key=filename)
        return True
    except:
        return False