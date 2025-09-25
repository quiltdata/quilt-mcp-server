variable "name" {
  description = "Base name used for resources (e.g., quilt-mcp)"
  type        = string
}

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC hosting the service"
  type        = string
}

variable "vpc_cidr_block" {
  description = "CIDR block of the VPC (used for egress rules)"
  type        = string
  default     = "10.0.0.0/16"
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for ECS tasks"
  type        = list(string)
}

variable "alb_listener_arn" {
  description = "ARN of the ALB listener that should forward MCP traffic"
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
  description = "Path pattern matched by the listener rule"
  type        = string
  default     = "/mcp/*"
}

variable "alb_security_group_ids" {
  description = "Security groups attached to the ALB which should be allowed inbound access"
  type        = list(string)
  default     = []
}

variable "ecs_cluster_arn" {
  description = "ARN of the ECS cluster"
  type        = string
}

variable "execution_role_arn" {
  description = "IAM role used by ECS for pulling images and writing logs"
  type        = string
}

variable "task_role_policy_json" {
  description = "Optional inline IAM policy JSON attached to the task role"
  type        = string
  default     = null
}

variable "container_image" {
  description = "Container image URI (ECR)"
  type        = string
}

variable "container_port" {
  description = "Container port exposed by the MCP server"
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
  description = "Desired task count"
  type        = number
  default     = 2
}

variable "environment_variables" {
  description = "Map of environment variables for the container"
  type        = map(string)
  default     = {}
}

variable "log_group_name" {
  description = "CloudWatch log group name. If null, one is created automatically"
  type        = string
  default     = null
}

variable "log_retention_in_days" {
  description = "Retention period for CloudWatch logs"
  type        = number
  default     = 30
}

variable "health_check_path" {
  description = "HTTP path used for target group and container health checks"
  type        = string
  default     = "/healthz"
}

variable "tags" {
  description = "Additional resource tags"
  type        = map(string)
  default     = {}
}

variable "enable_execute_command" {
  description = "Enable ECS Exec on the service"
  type        = bool
  default     = false
}

variable "secret_arns" {
  description = "List of secrets to inject into the MCP container"
  type = list(object({
    name = string
    arn  = string
  }))
  default = []
}

variable "egress_cidr_blocks" {
  description = "CIDR blocks permitted for outbound traffic from the MCP tasks"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
