from pathlib import Path


def test_mcp_terraform_module_includes_health_check():
    module_dir = Path("deploy/terraform/modules/mcp_server")
    assert module_dir.is_dir(), "MCP Terraform module directory must exist"

    main_tf = module_dir / "main.tf"
    assert main_tf.exists(), "MCP Terraform module must define main.tf"

    variables_tf = module_dir / "variables.tf"
    assert variables_tf.exists(), "Module variables must be declared"

    main_content = main_tf.read_text()
    vars_content = variables_tf.read_text()

    assert "aws_ecs_service" in main_content
    assert "health_check_path" in main_content
    assert '"/healthz"' in vars_content
