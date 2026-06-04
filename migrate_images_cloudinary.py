import os
import sys
from urllib.parse import urlparse

import mysql.connector
from dotenv import load_dotenv
from cloudinary.uploader import upload

load_dotenv()


def is_cloudinary_url(url: str) -> bool:
    if not url:
        return False
    return "cloudinary.com" in url or "res.cloudinary.com" in url


from typing import Optional

def extract_local_path(image_url: str) -> Optional[str]:

    """Convert stored /static/uploads/<filename> url into a local filesystem path."""
    if not image_url:
        return None

    # expected: /static/uploads/<filename>
    parsed = urlparse(image_url)
    path = parsed.path if parsed.scheme else image_url

    prefix = "/static/uploads/"
    if prefix in path:
        filename = path.split(prefix, 1)[1]
        base_dir = os.path.join(os.path.dirname(__file__), "static", "uploads")
        return os.path.join(base_dir, filename)

    return None


def main():
    mysql_host = os.getenv("MYSQL_HOST", "localhost")
    mysql_port = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_user = os.getenv("MYSQL_USER", "root")
    mysql_password = os.getenv("MYSQL_PASSWORD", "")
    mysql_database = os.getenv("MYSQL_DATABASE", "crackershub")

    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    upload_preset = os.getenv("CLOUDINARY_UPLOAD_PRESET")

    if not all([cloud_name, api_key, api_secret, upload_preset]):
        print("Missing Cloudinary env vars. Required: CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, CLOUDINARY_UPLOAD_PRESET")
        sys.exit(1)

    # configure cloudinary
    from cloudinary import config

    config.cloudinary_url = {
        "cloud_name": cloud_name,
        "api_key": api_key,
        "api_secret": api_secret,
    }

    # Connect DB
    conn = mysql.connector.connect(
        host=mysql_host,
        port=mysql_port,
        user=mysql_user,
        password=mysql_password,
        database=mysql_database,
    )
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, image_url FROM products WHERE image_url IS NOT NULL")
    rows = cursor.fetchall()

    updated = 0
    skipped = 0
    failed = 0

    for row in rows:
        product_id = row["id"]
        image_url = row["image_url"]

        if not image_url:
            continue

        if is_cloudinary_url(image_url):
            skipped += 1
            continue

        local_path = extract_local_path(image_url)
        if not local_path or not os.path.exists(local_path):
            print(f"[SKIP] product_id={product_id} missing local file for image_url={image_url}")
            failed += 1
            continue

        print(f"[UPLOADING] product_id={product_id} file={local_path}")
        try:
            result = upload(
                local_path,
                upload_preset=upload_preset,
                resource_type="image",
                folder="products",
            )
            secure_url = result.get("secure_url")
            if not secure_url:
                raise RuntimeError("No secure_url returned")

            cursor.execute(
                "UPDATE products SET image_url = %s WHERE id = %s",
                (secure_url, product_id),
            )
            updated += 1
            conn.commit()
        except Exception as e:
            print(f"[ERROR] product_id={product_id}: {e}")
            failed += 1

    cursor.close()
    conn.close()

    print(f"Done. updated={updated}, skipped={skipped}, failed={failed}")


if __name__ == "__main__":
    main()

