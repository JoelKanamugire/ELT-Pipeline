variable "env" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "bucket_name" {
  description = "Name of the S3 data lake bucket"
  type        = string
  default     = "cwo-dev-lake"
}