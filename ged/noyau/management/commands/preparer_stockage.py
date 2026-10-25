import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crée le bucket S3 de l'application s'il n'existe pas et vérifie qu'il n'est pas public."

    def handle(self, *args, **options):
        if not settings.GED_S3_ENDPOINT:
            self.stdout.write("Stockage local sur disque : rien à préparer.")
            return
        config = settings.STORAGES["default"]["OPTIONS"]
        client = boto3.client(
            "s3",
            endpoint_url=config["endpoint_url"],
            aws_access_key_id=config["access_key"],
            aws_secret_access_key=config["secret_key"],
            region_name=config["region_name"],
        )
        bucket = config["bucket_name"]
        try:
            client.head_bucket(Bucket=bucket)
            self.stdout.write(f"Bucket {bucket} présent.")
        except ClientError:
            client.create_bucket(Bucket=bucket)
            self.stdout.write(self.style.SUCCESS(f"Bucket {bucket} créé."))
        try:
            politique = client.get_bucket_policy(Bucket=bucket)
        except ClientError:
            politique = None
        if politique:
            client.delete_bucket_policy(Bucket=bucket)
            self.stdout.write(self.style.WARNING(f"Politique d'accès du bucket {bucket} supprimée (bucket privé)."))
