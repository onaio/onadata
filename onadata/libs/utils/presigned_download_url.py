
def generate_presigned_download_url(bucket_name: str, file_path: str, expiration: int = 3600):
        """
        Generates a presigned Download URL
        file_path :string: Path to the file in the S3 Bucket
        expirationg :integer: The duration in seconds that the URL should be valid for
        """
        try:
            response = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket_name, "Key": file_path},
                ExpiresIn=expiration,
            )
        except ClientError:
            return None
        return response
