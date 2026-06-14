variable "env" {
  description = "Environment name (dev or prod)"
  type        = string
}

variable "bucket_name" {
  description = "Name of the S3 data lake bucket"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}