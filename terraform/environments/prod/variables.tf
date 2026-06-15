variable "env" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "bucket_name" {
  description = "Name of the S3 data lake bucket"
  type        = string
  default     = "cwo-prod-lake"
}