locals {
  base_name          = var.name
  log_group_name     = coalesce(var.log_group_name, "/ecs/${var.name}")
  default_tags       = merge({ Service = var.name }, var.tags)
  default_environment = {
    FASTMCP_TRANSPORT = "http"
    FASTMCP_HOST      = "0.0.0.0"
    FASTMCP_PORT      = tostring(var.container_port)
  }
  environment = merge(local.default_environment, var.environment_variables)
  container_secrets = [
    for secret in var.secret_arns : {
      name      = secret.name
      valueFrom = secret.arn
    }
  ]
}

resource "aws_cloudwatch_log_group" "mcp" {
  name              = local.log_group_name
  retention_in_days = var.log_retention_in_days
  tags              = local.default_tags
}

resource "aws_iam_role" "task" {
  name = "${local.base_name}-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.default_tags
}

resource "aws_iam_role_policy" "task_inline" {
  count  = var.task_role_policy_json == null ? 0 : 1
  name   = "${local.base_name}-task-policy"
  role   = aws_iam_role.task.id
  policy = var.task_role_policy_json
}

resource "aws_security_group" "mcp" {
  name_prefix = "${local.base_name}-"
  vpc_id      = var.vpc_id
  description = "Security group for ${local.base_name}"

  dynamic "ingress" {
    for_each = var.alb_security_group_ids
    content {
      description     = "Allow MCP HTTP traffic from ALB"
      from_port       = var.container_port
      to_port         = var.container_port
      protocol        = "tcp"
      security_groups = [ingress.value]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = var.egress_cidr_blocks
  }

  tags = local.default_tags
}

resource "aws_lb_target_group" "mcp" {
  name        = substr("${local.base_name}-tg", 0, 32)
  port        = var.container_port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  health_check {
    path                = var.health_check_path
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 6
    matcher             = "200-399"
  }

  deregistration_delay = 30
  tags                 = local.default_tags
}

resource "aws_lb_listener_rule" "mcp" {
  listener_arn = var.alb_listener_arn
  priority     = var.listener_priority

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.mcp.arn
  }

  condition {
    host_header {
      values = [var.listener_host]
    }
  }

  condition {
    path_pattern {
      values = [var.listener_path]
    }
  }

  tags = local.default_tags
}

resource "aws_ecs_task_definition" "mcp" {
  family                   = local.base_name
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = tostring(var.cpu)
  memory                   = tostring(var.memory)
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "${local.base_name}"
      image     = var.container_image
      essential = true

      portMappings = [
        {
          containerPort = var.container_port
          hostPort       = var.container_port
          protocol       = "tcp"
        }
      ]

      environment = [
        for key, value in local.environment : {
          name  = key
          value = value
        }
      ]

      secrets = local.container_secrets

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.mcp.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://127.0.0.1:${var.container_port}${var.health_check_path} || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = local.default_tags
}

resource "aws_ecs_service" "mcp" {
  name            = local.base_name
  cluster         = var.ecs_cluster_arn
  task_definition = aws_ecs_task_definition.mcp.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"
  platform_version = "LATEST"

  load_balancer {
    target_group_arn = aws_lb_target_group.mcp.arn
    container_name   = local.base_name
    container_port   = var.container_port
  }

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.mcp.id]
    assign_public_ip = false
  }

  enable_execute_command = var.enable_execute_command

  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 50

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [
    aws_lb_listener_rule.mcp,
  ]

  tags = local.default_tags
}
