#!/bin/bash
# Configure Claude Code to use AWS Bedrock via the `claude` CLI
# - Requires: AWS CLI, jq, and the Claude Code CLI (`claude`)
# - Behavior: Detect region, verify Bedrock access, choose best Claude models available,
#             and write settings to Claude's global config via `claude config`
#
# References:
# * Claude Code on Amazon Bedrock: https://docs.anthropic.com/en/docs/claude-code/amazon-bedrock
# * Claude Code settings: https://docs.anthropic.com/en/docs/claude-code/settings

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$REPO_ROOT/shared/common.sh"

# -----------------------------------------------------------------------------
# Prerequisites and Environment Setup
# -----------------------------------------------------------------------------
check_bedrock_prereqs() {
  log_info "🔍 Checking prerequisites for Bedrock configuration..."
  
  # Check required tools using shared function
  check_dependencies "claude" "aws" "jq"
  
  # Validate AWS credentials
  if ! aws sts get-caller-identity >/dev/null 2>&1; then
    log_error "❌ AWS credentials not configured. Run: aws configure"
    exit 1
  fi
  
  local identity
  identity=$(aws sts get-caller-identity --output json)
  log_success "✅ AWS credentials valid"
  log_info "  Account: $(echo "$identity" | jq -r '.Account')"
  log_info "  User: $(echo "$identity" | jq -r '.Arn' | cut -d'/' -f2)"
}

get_bedrock_region() {
  # Use shared AWS defaults setup, but prefer explicit Bedrock-friendly regions
  local region="${AWS_REGION:-${AWS_DEFAULT_REGION:-${CDK_DEFAULT_REGION:-}}}"
  if [ -z "$region" ]; then
    region=$(aws configure get region 2>/dev/null || echo "us-east-1")
  fi
  
  log_info "🌍 Using AWS region: $region"
  echo "$region"
}

verify_bedrock_access() {
  local region="$1"
  log_info "🔐 Verifying Bedrock access in region: $region"
  
  if ! aws bedrock list-foundation-models --region "$region" >/dev/null 2>&1; then
    log_error "❌ Cannot access Amazon Bedrock in region $region"
    log_error "Ensure Bedrock is enabled and you have permissions:"
    log_error "  - bedrock:ListFoundationModels"
    log_error "  - bedrock:InvokeModel"
    exit 1
  fi
  
  log_success "✅ Bedrock access confirmed"
}

# -----------------------------------------------------------------------------
# Model Discovery and Selection
# -----------------------------------------------------------------------------
list_claude_models() {
  local region="$1"
  aws bedrock list-foundation-models \
    --region "$region" \
    --output json | \
    jq -r '.modelSummaries[] | select(.providerName=="Anthropic") | .modelId' | \
    sort -V
}

list_inference_profiles() {
  local region="$1"
  
  # List inference profiles with Claude models (preferred approach)
  if aws bedrock list-inference-profiles --region "$region" --output json 2>/dev/null | \
     jq -r '.inferenceProfileSummaries[] | select(.models[]?.modelArn | contains("claude")) | .inferenceProfileArn' | \
     sort; then
    return 0
  else
    return 1
  fi
}

score_claude_model() {
  local model_id="$1"
  local score=0
  
  # Claude 4 models (highest priority)
  if [[ "$model_id" =~ claude-opus-4 ]]; then
    score=1000
  elif [[ "$model_id" =~ claude-sonnet-4 ]]; then
    score=900
  elif [[ "$model_id" =~ claude-haiku-4 ]]; then
    score=800
  # Claude 3.7 models
  elif [[ "$model_id" =~ claude-3-7-sonnet ]]; then
    score=700
  # Claude 3.5 models  
  elif [[ "$model_id" =~ claude-3-5-sonnet ]]; then
    score=600
    # Prefer v2
    if [[ "$model_id" =~ v2 ]]; then score=$((score + 50)); fi
  elif [[ "$model_id" =~ claude-3-5-haiku ]]; then
    score=500
  # Claude 3 models
  elif [[ "$model_id" =~ claude-3-opus ]]; then
    score=400
  elif [[ "$model_id" =~ claude-3-sonnet ]]; then
    score=300
  elif [[ "$model_id" =~ claude-3-haiku ]]; then
    score=200
  # Older models
  elif [[ "$model_id" =~ claude-v2 ]]; then
    score=100
  elif [[ "$model_id" =~ claude-instant ]]; then
    score=50
  fi
  
  # Penalize context-limited versions
  if [[ "$model_id" =~ :[0-9]+k ]]; then
    score=$((score - 10))
  fi
  
  echo "$score"
}

is_fast_model() {
  local model_id="$1"
  [[ "$model_id" =~ haiku ]] || [[ "$model_id" =~ instant ]]
}

test_model_access() {
  local region="$1"
  local model_or_profile="$2"
  
  log_info "  Testing access to: $model_or_profile"
  
  local temp_response="/tmp/bedrock_test_$$"
  if aws bedrock-runtime invoke-model \
    --region "$region" \
    --cli-binary-format raw-in-base64-out \
    --model-id "$model_or_profile" \
    --content-type "application/json" \
    --accept "application/json" \
    --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}' \
    "$temp_response" >/dev/null 2>&1; then
    
    if [ -f "$temp_response" ] && jq -e '.content[0].text' "$temp_response" >/dev/null 2>&1; then
      local response_text
      response_text=$(jq -r '.content[0].text' "$temp_response")
      log_success "    ✅ Working (response: \"$response_text\")"
      rm -f "$temp_response"
      return 0
    fi
  fi
  
  log_warning "    ❌ Failed to access"
  rm -f "$temp_response"
  return 1
}

find_best_models() {
  local region="$1"
  
  log_info "🔍 Finding best available Claude models..."
  
  # Try inference profiles first (recommended approach)
  local profiles
  if profiles=$(list_inference_profiles "$region" 2>/dev/null) && [ -n "$profiles" ]; then
    log_info "  Found inference profiles (recommended approach)"
    
    local best_main="" best_fast="" best_score=0 best_fast_score=0
    
    while read -r profile; do
      if [ -z "$profile" ]; then continue; fi
      
      if test_model_access "$region" "$profile"; then
        local score
        score=$(score_claude_model "$profile")
        
        # Track best overall model
        if [ "$score" -gt "$best_score" ]; then
          best_score="$score"
          best_main="$profile"
        fi
        
        # Track best fast model
        if is_fast_model "$profile" && [ "$score" -gt "$best_fast_score" ]; then
          best_fast_score="$score"
          best_fast="$profile"
        fi
      fi
    done <<< "$profiles"
    
    # Use main model for fast if no dedicated fast model found
    if [ -z "$best_fast" ]; then
      best_fast="$best_main"
    fi
    
    if [ -n "$best_main" ]; then
      echo "$best_main|$best_fast"
      return 0
    fi
  fi
  
  # Fallback to direct model access
  log_info "  No inference profiles available, trying direct model access"
  local models
  models=$(list_claude_models "$region")
  
  local best_main="" best_fast="" best_score=0 best_fast_score=0
  
  while read -r model; do
    if [ -z "$model" ]; then continue; fi
    
    if test_model_access "$region" "$model"; then
      local score
      score=$(score_claude_model "$model")
      
      # Track best overall model
      if [ "$score" -gt "$best_score" ]; then
        best_score="$score"
        best_main="$model"
      fi
      
      # Track best fast model
      if is_fast_model "$model" && [ "$score" -gt "$best_fast_score" ]; then
        best_fast_score="$score"
        best_fast="$model"
      fi
    fi
  done <<< "$models"
  
  # Use main model for fast if no dedicated fast model found
  if [ -z "$best_fast" ]; then
    best_fast="$best_main"
  fi
  
  if [ -n "$best_main" ]; then
    echo "$best_main|$best_fast"
    return 0
  fi
  
  log_error "❌ No working Claude models found"
  return 1
}

# -----------------------------------------------------------------------------
# Claude Configuration
# -----------------------------------------------------------------------------
backup_claude_config() {
  local backup_dir="$HOME/.claude/backups"
  local backup_file="$backup_dir/settings_backup_$(date +%Y%m%d_%H%M%S).json"
  
  if [ -f "$HOME/.claude/settings.json" ]; then
    mkdir -p "$backup_dir"
    cp "$HOME/.claude/settings.json" "$backup_file"
    echo "$backup_file"
  else
    echo ""
  fi
}

configure_claude_for_bedrock() {
  local region="$1"
  local main_model="$2"
  local fast_model="$3"
  
  log_info "⚙️  Applying Claude configuration for Bedrock..."
  
  # Backup existing configuration
  local backup_file
  backup_file=$(backup_claude_config)
  if [ -n "$backup_file" ]; then
    log_info "  📁 Created backup: $backup_file"
  fi
  
  # Set environment variables via claude config
  claude config set --global env.CLAUDE_CODE_USE_BEDROCK "1" >/dev/null
  claude config set --global env.AWS_REGION "$region" >/dev/null
  claude config set --global env.ANTHROPIC_MODEL "$main_model" >/dev/null
  claude config set --global env.ANTHROPIC_SMALL_FAST_MODEL "$fast_model" >/dev/null
  claude config set --global env.ANTHROPIC_SMALL_FAST_MODEL_AWS_REGION "$region" >/dev/null
  
  log_success "✅ Claude configuration updated"
  log_info "  🌍 Region: $region"
  log_info "  🧠 Main model: $main_model"
  log_info "  ⚡ Fast model: $fast_model"
  
  echo "$backup_file"
}

test_claude_with_bedrock() {
  log_info "🧪 Testing Claude CLI with Bedrock configuration..."
  
  local test_response
  if test_response=$(timeout 30 claude --print "Say 'Hello from Bedrock' and nothing else" 2>&1); then
    if echo "$test_response" | grep -q "Hello from Bedrock"; then
      log_success "✅ Claude CLI working with Bedrock!"
      log_info "  Response: $(echo "$test_response" | head -1)"
      return 0
    fi
  fi
  
  log_error "❌ Claude CLI test failed"
  log_error "  Response: $test_response"
  return 1
}

restore_claude_config() {
  local backup_file="$1"
  if [ -n "$backup_file" ] && [ -f "$backup_file" ]; then
    log_warning "🔄 Restoring Claude configuration from backup..."
    cp "$backup_file" "$HOME/.claude/settings.json"
    log_success "✅ Configuration restored"
  fi
}

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------
main() {
  log_info "🚀 Configuring Claude Code to use Amazon Bedrock"
  echo ""
  
  # Load environment if available (non-fatal)
  load_environment 2>/dev/null || true
  
  # Check prerequisites
  check_bedrock_prereqs
  
  # Setup region and verify Bedrock access
  local region
  region=$(get_bedrock_region)
  verify_bedrock_access "$region"
  
  # Find best available models
  local model_selection
  if ! model_selection=$(find_best_models "$region"); then
    log_error "❌ No suitable Claude models found"
    exit 1
  fi
  
  local main_model="${model_selection%%|*}"
  local fast_model="${model_selection##*|}"
  
  log_success "🎯 Selected models:"
  log_info "  🧠 Main: $main_model"
  log_info "  ⚡ Fast: $fast_model"
  echo ""
  
  # Configure Claude
  local backup_file
  backup_file=$(configure_claude_for_bedrock "$region" "$main_model" "$fast_model")
  
  # Test configuration
  if test_claude_with_bedrock; then
    # Clean up backup on success
    if [ -n "$backup_file" ] && [ -f "$backup_file" ]; then
      rm -f "$backup_file"
    fi
    
    echo ""
    log_success "🎉 Setup complete!"
    log_info "  💡 You can now use Claude with Bedrock"
    log_info "  🔧 Verify with: claude config get --global env"
    log_info "  🗣️  Start REPL: claude"
  else
    log_error "❌ Setup failed - reverting configuration"
    restore_claude_config "$backup_file"
    exit 1
  fi
}

# Run main function
main "$@"
