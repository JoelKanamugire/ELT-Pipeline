variable "bucket_arn" {
  description = "ARN of the S3 bucket this policy grants access to"
  type        = string
}

variable "env" {
  description = "Environment name, used to make the policy name unique (dev/prod)"
  type        = string
}

variable "cicd_user_name" {
  description = "Name of the existing IAM user used by CI/CD"
  type        = string
  default     = "cwo-cicd"
}

data "aws_iam_user" "cicd" {
  user_name = var.cicd_user_name
}


resource "aws_iam_policy" "cwo_lake_access" {
  name        = "cwo-${var.env}-lake-s3-access"
  description = "Least-privilege S3 access for the ${var.env} CWO data lake bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [var.bucket_arn]
      },
      {
        Sid      = "ReadWriteObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = ["${var.bucket_arn}/*"]
      }

    ]
  })
}


resource "aws_iam_user_policy_attachment" "cicd_lake_access" {
  user       = data.aws_iam_user.cicd.user_name
  policy_arn = aws_iam_policy.cwo_lake_access.arn
}

resource "aws_iam_policy" "terraform_backend_access" {
  name        = "cwo-${var.env}-terraform-backend-access"
  description = "Access to Terraform state bucket and lock table for ${var.env}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "StateBucketAccess"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = ["arn:aws:s3:::datadevp-tfstate/${var.env}/terraform.tfstate"]
      },
      {
        Sid      = "StateBucketList"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = ["arn:aws:s3:::datadevp-tfstate"]
      },
      {
        Sid      = "LockTableAccess"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"]
        Resource = ["arn:aws:dynamodb:us-east-2:625144383094:table/datadevp-tfstate-lock"]
      }
    ]
  })
}

resource "aws_iam_user_policy_attachment" "cicd_backend_access" {
  user       = data.aws_iam_user.cicd.user_name
  policy_arn = aws_iam_policy.terraform_backend_access.arn
}

resource "aws_iam_policy" "self_lookup" {
  name        = "cwo-${var.env}-iam-self-lookup"
  description = "Allows the CI/CD user to look up its own IAM user details"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "SelfGetUser"
        Effect   = "Allow"
        Action   = ["iam:GetUser"]
        Resource = ["arn:aws:iam::625144383094:user/${var.cicd_user_name}"]
      }
    ]
  })
}

resource "aws_iam_user_policy_attachment" "cicd_self_lookup" {
  user       = data.aws_iam_user.cicd.user_name
  policy_arn = aws_iam_policy.self_lookup.arn
}