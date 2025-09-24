variable "stack_name" {
  description = "Name prefix for the Quilt stack (e.g., sales-prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
}

variable "vpc_id" {
  description = "Target VPC ID"
  type        = string
}

variable "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for ECS tasks"
  type        = list(string)
}

variable "alb_listener_arn" {
  description = "ARN of the ALB listener"
  type        = string
}

variable "listener_priority" {
  description = "Priority for the MCP listener rule"
  type        = number
}

variable "listener_host" {
  description = "Host header value matched by the listener rule"
  type        = string
}

variable "listener_path" {
  description = "Path pattern for MCP traffic"
  type        = string
  default     = "/mcp/*"
}

variable "alb_security_group_ids" {
  description = "Security groups attached to the ALB allowed inbound access"
  type        = list(string)
  default     = []
}

variable "ecs_cluster_arn" {
  description = "ARN of the ECS cluster"
  type        = string
}

variable "execution_role_arn" {
  description = "IAM role used by ECS for pulling images/writing logs"
  type        = string
}

variable "task_policy_json" {
  description = "Optional IAM policy JSON attached to the MCP task role"
  type        = string
  default     = null
}

variable "container_image" {
  description = "Container image URI (ECR)"
  type        = string
}

variable "container_port" {
  description = "Container port"
  type        = number
  default     = 8000
}

variable "cpu" {
  description = "Fargate CPU units"
  type        = number
  default     = 512
}

variable "memory" {
  description = "Fargate memory (MiB)"
  type        = number
  default     = 1024
}

variable "desired_count" {
  description = "Desired ECS task count"
  type        = number
  default     = 2
}

variable "environment_variables" {
  description = "Additional environment variables for the MCP container"
  type        = map(string)
  default     = {}
}

variable "log_retention_in_days" {
  description = "Retention period for CloudWatch logs"
  type        = number
  default     = 30
}

variable "health_check_path" {
  description = "HTTP path used for ALB and container health checks"
  type        = string
  default     = "/healthz"
}

variable "enable_execute_command" {
  description = "Enable ECS Exec"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Additional tags applied to created resources"
  type        = map(string)
  default     = {}
}
