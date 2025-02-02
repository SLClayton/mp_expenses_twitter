### VARIABLES ###
variable "PROJECT_NAME" {
  description = "project name"
  type        = string
  default     = "mpexpenses-tweeter"
}

variable "AWS_REGION" {
  type        = string
  default     = "us-east-1"
}


### PROVIDERS ###
terraform {
  required_version = ">= 0.14"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "tf-state-mpexpenses-tweeter"
    key    = "terraform-state"
    region = "us-east-1"
  }
}


provider "aws" {
  region = var.AWS_REGION
  default_tags {
      tags = {
        project = var.PROJECT_NAME
    }
  }
}


### Build Script ###
resource "null_resource" "build_lambda" {
  triggers = {
    always_run = "${timestamp()}"
  }

  provisioner "local-exec" {
    command = "sh ../build_lambda.sh ${var.PROJECT_NAME}"
  }
}

data "archive_file" "lambda_package" {
  type        = "zip"
  source_dir = "../temp_build_dir/"
  output_path = "../packages/${var.PROJECT_NAME}.zip"

  depends_on = [null_resource.build_lambda]
}


resource "null_resource" "build_lambda_cleanup" {
  triggers = {
    always_run = "${timestamp()}"
  }

  provisioner "local-exec" {
    command = "sh ../build_lambda_cleanup.sh"
  }

  depends_on = [data.archive_file.lambda_package]
}



### IAM ROLE & POLICIES FOR LAMBDA ###
resource "aws_iam_role" "lambda_iam_role" {
  name = "${var.PROJECT_NAME}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Principal = {
          Service = "lambda.amazonaws.com"
        },
        Effect = "Allow",
        Sid = ""
      }
    ]
  })
}

data "aws_secretsmanager_secret" "twitter_secret" {
  name = "mpexpenses-twitter-credentials"
}

resource "aws_dynamodb_table" "past_tweets_table" {
  name           = "${var.PROJECT_NAME}-past-tweets"
  billing_mode   = "PAY_PER_REQUEST"

  attribute {
    name = "expense_id"
    type = "S"
  }
  hash_key = "expense_id"
}

resource "aws_iam_policy" "lambda_policy" {
  name        = "${var.PROJECT_NAME}-lambda-policy"
  description = "Policy for ${var.PROJECT_NAME} lambda"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action   = "secretsmanager:GetSecretValue",
        Effect   = "Allow",
        Resource = data.aws_secretsmanager_secret.twitter_secret.arn
      },
      {
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem"
        ],
        Effect   = "Allow",
        Resource = aws_dynamodb_table.past_tweets_table.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_lambda_policy_to_role" {
  role       = aws_iam_role.lambda_iam_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

resource "aws_iam_role_policy_attachment" "basic_execution_policy_attachment" {
  role       = aws_iam_role.lambda_iam_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}


###  LAMBDA FUNCTIONS  ###
resource "aws_lambda_function" "lambda_function" {
  function_name = "${var.PROJECT_NAME}-lambda-function"
  filename      = data.archive_file.lambda_package.output_path
  role          = aws_iam_role.lambda_iam_role.arn
  runtime       = "python3.10"
  handler       = "lambda_function.lambda_handler"
  timeout       = 90
  memory_size   = 1028
  source_code_hash = data.archive_file.lambda_package.output_base64sha256

  environment {
    variables = {
      MPE_TWITTER_SECRET_NAME = data.aws_secretsmanager_secret.twitter_secret.name
      MPE_DDB_TABLE_NAME = aws_dynamodb_table.past_tweets_table.name
    }
  }

  depends_on = [null_resource.build_lambda]
}


resource "aws_cloudwatch_event_rule" "trigger_every_hour" {
  name        = "${var.PROJECT_NAME}-lambda-trigger"
  description = "Triggers the Lambda function every hour"
  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.trigger_every_hour.name
  target_id = "${var.PROJECT_NAME}-lambda-target"
  arn       = aws_lambda_function.lambda_function.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda_function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.trigger_every_hour.arn
}

