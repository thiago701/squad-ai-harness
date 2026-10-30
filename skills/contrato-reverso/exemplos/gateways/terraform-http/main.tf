# Task Manager — o MESMO Gateway do template SAM (app/template.yaml), escrito em Terraform.
# Fixture de paridade do leitor terraform-hcl da skill contrato-reverso.
variable "cors_allowed_origins" {
  type    = list(string)
  default = ["https://painel.exemplo.local"]
}

variable "stage_name" {
  type    = string
  default = "prod"
}

resource "aws_lambda_function" "task" {
  function_name = "task-manager"
  runtime       = "java25"
  handler       = "com.squadai.taskmanager.api.TaskApiGatewayHandler::handleRequest"
  timeout       = 10
  memory_size   = 512
  role          = aws_iam_role.task.arn # papel de execução fora do escopo da fixture
}

resource "aws_apigatewayv2_api" "task" {
  name          = "task-manager"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins     = var.cors_allowed_origins
    allow_methods     = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
    allow_headers     = ["authorization", "content-type"]
    allow_credentials = false
    max_age           = 600
  }
}

resource "aws_apigatewayv2_authorizer" "cognito_jwt" {
  api_id           = aws_apigatewayv2_api.task.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "CognitoJwt"
  jwt_configuration {
    audience = [aws_cognito_user_pool_client.task.id]
    issuer   = "https://cognito-idp.${data.aws_region.atual.name}.amazonaws.com/${aws_cognito_user_pool.task.id}"
  }
}

resource "aws_apigatewayv2_integration" "task" {
  api_id                 = aws_apigatewayv2_api.task.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.task.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.task.id
  name        = var.stage_name
  auto_deploy = true
  default_route_settings {
    throttling_burst_limit = 50
    throttling_rate_limit  = 100
  }
}

resource "aws_apigatewayv2_route" "create_task" {
  api_id             = aws_apigatewayv2_api.task.id
  route_key          = "POST /tasks"
  target             = "integrations/${aws_apigatewayv2_integration.task.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito_jwt.id
}

resource "aws_apigatewayv2_route" "list_tasks" {
  api_id             = aws_apigatewayv2_api.task.id
  route_key          = "GET /tasks"
  target             = "integrations/${aws_apigatewayv2_integration.task.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito_jwt.id
}

resource "aws_apigatewayv2_route" "get_task" {
  api_id             = aws_apigatewayv2_api.task.id
  route_key          = "GET /tasks/{taskId}"
  target             = "integrations/${aws_apigatewayv2_integration.task.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito_jwt.id
}

resource "aws_apigatewayv2_route" "update_task" {
  api_id             = aws_apigatewayv2_api.task.id
  route_key          = "PATCH /tasks/{taskId}"
  target             = "integrations/${aws_apigatewayv2_integration.task.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito_jwt.id
}

resource "aws_apigatewayv2_route" "delete_task" {
  api_id             = aws_apigatewayv2_api.task.id
  route_key          = "DELETE /tasks/{taskId}"
  target             = "integrations/${aws_apigatewayv2_integration.task.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito_jwt.id
}

resource "aws_apigatewayv2_route" "transition_task" {
  api_id             = aws_apigatewayv2_api.task.id
  route_key          = "POST /tasks/{taskId}/transitions"
  target             = "integrations/${aws_apigatewayv2_integration.task.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito_jwt.id
}

resource "aws_apigatewayv2_route" "task_summary" {
  api_id             = aws_apigatewayv2_api.task.id
  route_key          = "GET /tasks/summary"
  target             = "integrations/${aws_apigatewayv2_integration.task.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito_jwt.id
}
