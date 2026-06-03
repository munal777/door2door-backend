from storages.backends.s3boto3 import S3Boto3Storage

class DocumentStorage(S3Boto3Storage):
    location     = 'docs'
    file_overwrite = False

class ProofOfDeliveryStorage(S3Boto3Storage):
    location     = 'pod'
    file_overwrite = False

class CourierLogoStorage(S3Boto3Storage):
    location     = 'logo'
    file_overwrite = False

class ProfileStorage(S3Boto3Storage):
    location     = 'profile'
    file_overwrite = False