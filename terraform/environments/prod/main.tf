# This is the backend config — tells Terraform to store state in S3
terraform {
  backend "s3" {
    bucket         = "datadevp-tfstate"       # the bucket we just created
    key            = "prod/terraform.tfstate" # path inside the bucket
    region         = "us-east-2"
    dynamodb_table = "datadevp-tfstate-lock" # the lock table we created
    encrypt        = true                    # encrypts the state file
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Tell Terraform which AWS region to use
provider "aws" {
  region  = "us-east-2"
}

# Call our S3 data lake module
module "s3_lake" {
  source      = "../../modules/s3"
  env         = "prod"
  bucket_name = "cwo-prod-lake"

  tags = {
    Environment = "prod"
    Project     = "datadevp"
  }
}
# Read dev's state remotely, just to grab its bucket ARN — read-only, changes nothing in dev
data "terraform_remote_state" "dev" {
  backend = "s3"
  config = {
    bucket = "datadevp-tfstate"
    key    = "dev/terraform.tfstate"
    region = "us-east-2"
  }
}

module "iam" {
  source     = "../../modules/iam"
  env        = "prod"
  bucket_arn = module.s3_lake.bucket_arn
}