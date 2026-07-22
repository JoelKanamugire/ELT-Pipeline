# Create the S3 data lake bucket
resource "aws_s3_bucket" "lake" {
  bucket = var.bucket_name

  tags = var.tags
}

# Turn on versioning — lets you recover deleted/overwritten files
resource "aws_s3_bucket_versioning" "lake" {
  bucket = aws_s3_bucket.lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Block all public access — this is private data, never public
resource "aws_s3_bucket_public_access_block" "lake" {
  bucket                  = aws_s3_bucket.lake.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Encrypt everything stored in the bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "lake" {
  bucket = aws_s3_bucket.lake.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
# Create the folder structure inside the bucket
resource "aws_s3_object" "folders" {
  for_each = toset(["raw/", "silver/", "gold/", "scripts/", "logs/"])
  bucket   = aws_s3_bucket.lake.id
  key      = each.value
}