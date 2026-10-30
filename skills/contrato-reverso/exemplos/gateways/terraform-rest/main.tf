# Task Manager em REST API (v1) com Terraform — fixture de paridade do leitor terraform-hcl (REST).
resource "aws_lambda_function" "task" {
  function_name = "task-manager"
  handler       = "com.squadai.taskmanager.api.TaskRestHandler::handleRequest"
  runtime       = "java25"
  timeout       = 10
}

resource "aws_api_gateway_rest_api" "task" {
  name = "task-manager"
}

resource "aws_api_gateway_authorizer" "cognito" {
  name          = "CognitoAuth"
  rest_api_id   = aws_api_gateway_rest_api.task.id
  type          = "COGNITO_USER_POOLS"
  provider_arns = [aws_cognito_user_pool.task.arn]
}

resource "aws_api_gateway_resource" "tasks" {
  rest_api_id = aws_api_gateway_rest_api.task.id
  parent_id   = aws_api_gateway_rest_api.task.root_resource_id
  path_part   = "tasks"
}

resource "aws_api_gateway_resource" "task_id" {
  rest_api_id = aws_api_gateway_rest_api.task.id
  parent_id   = aws_api_gateway_resource.tasks.id
  path_part   = "{taskId}"
}

resource "aws_api_gateway_resource" "transitions" {
  rest_api_id = aws_api_gateway_rest_api.task.id
  parent_id   = aws_api_gateway_resource.task_id.id
  path_part   = "transitions"
}

resource "aws_api_gateway_resource" "summary" {
  rest_api_id = aws_api_gateway_rest_api.task.id
  parent_id   = aws_api_gateway_resource.tasks.id
  path_part   = "summary"
}

locals {
  # (método, recurso) — um aws_api_gateway_method por linha abaixo
}

resource "aws_api_gateway_method" "post_tasks" {
  rest_api_id   = aws_api_gateway_rest_api.task.id
  resource_id   = aws_api_gateway_resource.tasks.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_method" "get_tasks" {
  rest_api_id   = aws_api_gateway_rest_api.task.id
  resource_id   = aws_api_gateway_resource.tasks.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_method" "get_task" {
  rest_api_id   = aws_api_gateway_rest_api.task.id
  resource_id   = aws_api_gateway_resource.task_id.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_method" "patch_task" {
  rest_api_id   = aws_api_gateway_rest_api.task.id
  resource_id   = aws_api_gateway_resource.task_id.id
  http_method   = "PATCH"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_method" "delete_task" {
  rest_api_id   = aws_api_gateway_rest_api.task.id
  resource_id   = aws_api_gateway_resource.task_id.id
  http_method   = "DELETE"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_method" "post_transition" {
  rest_api_id   = aws_api_gateway_rest_api.task.id
  resource_id   = aws_api_gateway_resource.transitions.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_method" "get_summary" {
  rest_api_id   = aws_api_gateway_rest_api.task.id
  resource_id   = aws_api_gateway_resource.summary.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "post_tasks" {
  rest_api_id             = aws_api_gateway_rest_api.task.id
  resource_id             = aws_api_gateway_resource.tasks.id
  http_method             = "POST"
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = aws_lambda_function.task.invoke_arn
}

resource "aws_api_gateway_integration" "get_tasks" {
  rest_api_id             = aws_api_gateway_rest_api.task.id
  resource_id             = aws_api_gateway_resource.tasks.id
  http_method             = "GET"
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = aws_lambda_function.task.invoke_arn
}

resource "aws_api_gateway_integration" "get_task" {
  rest_api_id             = aws_api_gateway_rest_api.task.id
  resource_id             = aws_api_gateway_resource.task_id.id
  http_method             = "GET"
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = aws_lambda_function.task.invoke_arn
}

resource "aws_api_gateway_integration" "patch_task" {
  rest_api_id             = aws_api_gateway_rest_api.task.id
  resource_id             = aws_api_gateway_resource.task_id.id
  http_method             = "PATCH"
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = aws_lambda_function.task.invoke_arn
}

resource "aws_api_gateway_integration" "delete_task" {
  rest_api_id             = aws_api_gateway_rest_api.task.id
  resource_id             = aws_api_gateway_resource.task_id.id
  http_method             = "DELETE"
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = aws_lambda_function.task.invoke_arn
}

resource "aws_api_gateway_integration" "post_transition" {
  rest_api_id             = aws_api_gateway_rest_api.task.id
  resource_id             = aws_api_gateway_resource.transitions.id
  http_method             = "POST"
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = aws_lambda_function.task.invoke_arn
}

resource "aws_api_gateway_integration" "get_summary" {
  rest_api_id             = aws_api_gateway_rest_api.task.id
  resource_id             = aws_api_gateway_resource.summary.id
  http_method             = "GET"
  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = aws_lambda_function.task.invoke_arn
}

resource "aws_api_gateway_method" "options_tasks" {
  rest_api_id   = aws_api_gateway_rest_api.task.id
  resource_id   = aws_api_gateway_resource.tasks.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_tasks" {
  rest_api_id       = aws_api_gateway_rest_api.task.id
  resource_id       = aws_api_gateway_resource.tasks.id
  http_method       = "OPTIONS"
  type              = "MOCK"
  request_templates = { "application/json" = "{\"statusCode\": 200}" }
}

resource "aws_api_gateway_integration_response" "options_tasks" {
  rest_api_id = aws_api_gateway_rest_api.task.id
  resource_id = aws_api_gateway_resource.tasks.id
  http_method = "OPTIONS"
  status_code = "204"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = "'https://painel.exemplo.local'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Headers" = "'authorization,content-type'"
  }
}

resource "aws_api_gateway_stage" "prod" {
  rest_api_id   = aws_api_gateway_rest_api.task.id
  deployment_id = aws_api_gateway_deployment.task.id
  stage_name    = "prod"
}

resource "aws_api_gateway_method_settings" "todos" {
  rest_api_id = aws_api_gateway_rest_api.task.id
  stage_name  = aws_api_gateway_stage.prod.stage_name
  method_path = "*/*"
  settings {
    throttling_burst_limit = 50
    throttling_rate_limit  = 100
  }
}
