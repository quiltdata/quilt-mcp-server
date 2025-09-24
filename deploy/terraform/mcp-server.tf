module "mcp_server" {
  source = "./modules/mcp_server"

  name                 = "${var.stack_name}-mcp-server"
  aws_region           = var.aws_region
  vpc_id               = var.vpc_id
  vpc_cidr_block       = var.vpc_cidr_block
  private_subnet_ids   = var.private_subnet_ids
  alb_listener_arn     = var.alb_listener_arn
  listener_priority    = var.listener_priority
  listener_host        = var.listener_host
  listener_path        = var.listener_path
  alb_security_group_ids = var.alb_security_group_ids
  ecs_cluster_arn      = var.ecs_cluster_arn
  execution_role_arn   = var.execution_role_arn
  task_role_policy_json = var.task_policy_json
  container_image      = var.container_image
  container_port       = var.container_port
  cpu                  = var.cpu
  memory               = var.memory
  desired_count        = var.desired_count
  environment_variables = var.environment_variables
  log_retention_in_days = var.log_retention_in_days
  health_check_path     = var.health_check_path
  enable_execute_command = var.enable_execute_command
  tags                  = merge({ Environment = var.stack_name }, var.tags)
}

output "mcp_service_name" {
  description = "Name of the deployed MCP ECS service"
  value       = module.mcp_server.service_name
}

output "mcp_target_group_arn" {
  description = "Target group ARN receiving MCP traffic"
  value       = module.mcp_server.target_group_arn
}

output "mcp_security_group_id" {
  description = "Security group protecting MCP tasks"
  value       = module.mcp_server.security_group_id
}
