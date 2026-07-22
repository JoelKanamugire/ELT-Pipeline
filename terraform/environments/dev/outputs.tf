output "bucket_arn" {
  description = "ARN of the dev data lake bucket, exposed for other states to reference"
  value       = module.s3_lake.bucket_arn
}