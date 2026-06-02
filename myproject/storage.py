from storages.backends.s3boto3 import S3Boto3Storage

class DocumentStorage(S3Boto3Storage):
    location     = 'docs'
    file_overwrite = False

class ProofOfDeliveryStorage(S3Boto3Storage):
    location     = 'pod'
    file_overwrite = False