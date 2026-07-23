# staff_routes.py
from flask import Blueprint, request, jsonify
import boto3
from botocore.exceptions import NoCredentialsError, ClientError

aws_bp = Blueprint("aws_bp", __name__)

AWS_ACCESS_KEY = "AKIA5QZ6C722GTBGTXE6"
AWS_SECRET_KEY = "V+0N4EbpM9mwyoeaXTWQa32Tty+1623X73CEdH5O"
AWS_REGION = "eu-north-1"  # e.g. ap-south-1 for Mumbai
S3_BUCKET = "poultry-files-bucket"

# Initialize boto3 client
s3 = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)

# -----------------------------
# Upload endpoint
# -----------------------------
@aws_bp.route('/upload', methods=['POST'])
def upload_file():
    if 'image' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['image']

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        # Define the S3 file path
        s3_file_name = f"newpoultryhub/expensebill/{file.filename}"

        # Upload file to S3
        s3.upload_fileobj(
            Fileobj=file,
            Bucket=S3_BUCKET,
            Key=s3_file_name,
            ExtraArgs={'ContentType': file.content_type}
        )

        # Public URL of the uploaded file
        file_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{s3_file_name}"

        return jsonify({'message': 'File uploaded successfully', 'url': file_url}), 200

    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404
    except NoCredentialsError:
        return jsonify({'error': 'AWS credentials not available'}), 403
    except ClientError as e:
        return jsonify({'error': str(e)}), 500
    
