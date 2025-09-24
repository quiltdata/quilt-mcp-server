output "service_name" {
  description = "Name of the ECS service"
  value       = aws_ecs_service.mcp.name
}

output "task_role_arn" {
  description = "IAM role ARN used by the task"
  value       = aws_iam_role.task.arn
}

output "security_group_id" {
  description = "Security group protecting the MCP service"
  value       = aws_security_group.mcp.id
}

output "target_group_arn" {
  description = "Target group ARN receiving ALB traffic"
  value       = aws_lb_target_group.mcp.arn
}

output "listener_rule_arn" {
  description = "ALB listener rule forwarding MCP traffic"
  value       = aws_lb_listener_rule.mcp.arn
}

output "log_group_name" {
  description = "CloudWatch log group name for container logs"
  value       = aws_cloudwatch_log_group.mcp.name
}
