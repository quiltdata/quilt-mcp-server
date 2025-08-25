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
  
  log_info "🌍 Using AWS region: $region" >&2
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

parse_claude_model() {
  local model_id="$1"
  
  # Initialize variables
  local type="" version="" date="" context="" variant=""
  
  # Extract model from inference profile ARN if needed
  if [[ "$model_id" =~ inference-profile ]]; then
    # Extract the actual model name from inference profile
    if [[ "$model_id" =~ anthropic\.claude-([^/:]+) ]]; then
      model_id="anthropic.claude-${BASH_REMATCH[1]}"
    fi
  fi
  
  # Parse Bedrock format: anthropic.claude-{version}-{type}-{date}-{variant}:{context}
  if [[ "$model_id" =~ anthropic\.claude-([0-9]+)-([0-9]+)-([^-:]+)-([0-9]{8})-([^:]+)(:([0-9]+k))? ]]; then
    version="${BASH_REMATCH[1]}-${BASH_REMATCH[2]}"
    type="${BASH_REMATCH[3]}"
    date="${BASH_REMATCH[4]}"
    variant="${BASH_REMATCH[5]}"
    context="${BASH_REMATCH[7]}"
  # Parse format: anthropic.claude-{version}-{type}-{date}:{context}
  elif [[ "$model_id" =~ anthropic\.claude-([0-9]+)-([0-9]+)-([^-:]+)-([0-9]{8})(:([0-9]+k))? ]]; then
    version="${BASH_REMATCH[1]}-${BASH_REMATCH[2]}"
    type="${BASH_REMATCH[3]}"
    date="${BASH_REMATCH[4]}"
    context="${BASH_REMATCH[6]}"
  # Parse NEW format: anthropic.claude-{type}-{version}-{date}-{variant}:{context}
  elif [[ "$model_id" =~ anthropic\.claude-([^-]+)-([0-9]+)-([0-9]{8})-([^:]+)(:([0-9]+k))? ]]; then
    type="${BASH_REMATCH[1]}"
    version="${BASH_REMATCH[2]}"
    date="${BASH_REMATCH[3]}"
    variant="${BASH_REMATCH[4]}"
    context="${BASH_REMATCH[6]}"
  # Parse legacy format: anthropic.claude-{type}:{context} or anthropic.claude-{type}-{variant}:{context}
  elif [[ "$model_id" =~ anthropic\.claude-([^-:]+)(-([^:]+))?(:([0-9]+k))? ]]; then
    type="${BASH_REMATCH[1]}"
    variant="${BASH_REMATCH[3]}"
    context="${BASH_REMATCH[5]}"
  # Handle standard formats: claude-{version}-{type}
  elif [[ "$model_id" =~ claude-([0-9]+-?[0-9]*)-([^-:]+)(-([^:]+))?(:([0-9]+k))? ]]; then
    version="${BASH_REMATCH[1]}"
    type="${BASH_REMATCH[2]}"
    variant="${BASH_REMATCH[4]}"
    context="${BASH_REMATCH[6]}"
  # Handle very old formats: claude-v2, claude-instant
  elif [[ "$model_id" =~ claude-(v[0-9]+|instant)(-([^:]+))?(:([0-9]+k))? ]]; then
    version="${BASH_REMATCH[1]}"
    type="legacy"
    variant="${BASH_REMATCH[3]}"
    context="${BASH_REMATCH[5]}"
  # Handle new formats: claude-{type}-{major}.{minor}
  elif [[ "$model_id" =~ claude-([^-]+)-([0-9]+\.[0-9]+)(-([^:]+))?(:([0-9]+k))? ]]; then
    type="${BASH_REMATCH[1]}"
    version="${BASH_REMATCH[2]}"
    variant="${BASH_REMATCH[4]}"
    context="${BASH_REMATCH[6]}"
  fi
  
  # Extract date from variant if it looks like a date (YYYYMMDD)
  if [[ "$variant" =~ ^[0-9]{8}$ ]]; then
    date="$variant"
    variant=""
  elif [[ "$variant" =~ ^([0-9]{8})-(.+)$ ]]; then
    date="${BASH_REMATCH[1]}"
    variant="${BASH_REMATCH[2]}"
  fi
  
  # Output in format: type|version|date|variant|context
  echo "${type:-unknown}|${version:-0}|${date:-00000000}|${variant:-}|${context:-}"
}

version_to_numeric() {
  local version="$1"
  
  # Handle different version formats
  if [[ "$version" =~ ^([0-9]+)\.([0-9]+)$ ]]; then
    # Format: 4.0, 3.5
    echo $(( ${BASH_REMATCH[1]} * 1000 + ${BASH_REMATCH[2]} * 100 ))
  elif [[ "$version" =~ ^([0-9]+)-([0-9]+)$ ]]; then
    # Format: 3-5 
    echo $(( ${BASH_REMATCH[1]} * 1000 + ${BASH_REMATCH[2]} * 100 ))
  elif [[ "$version" =~ ^([0-9]+)$ ]]; then
    # Format: 4, 3
    echo $(( $1 * 1000 ))
  elif [[ "$version" =~ ^v([0-9]+)$ ]]; then
    # Format: v2
    echo $(( ${BASH_REMATCH[1]} * 100 ))
  else
    echo 0
  fi
}

date_to_numeric() {
  local date="$1"
  
  if [[ "$date" =~ ^[0-9]{8}$ ]]; then
    echo "$date"
  else
    echo "00000000"
  fi
}

score_claude_model() {
  local model_id="$1"
  
  # Parse the model components
  local parsed
  parsed=$(parse_claude_model "$model_id")
  IFS='|' read -r type version date variant context <<< "$parsed"
  
  # Skip older/legacy models entirely
  if [[ "$type" =~ ^(legacy|v2|instant|claude-instant)$ ]] || [[ "$model_id" =~ claude-(v[0-9]+|instant) ]]; then
    echo "0"
    return
  fi
  
  # Base scoring: Opus > Sonnet > Haiku (hardcoded hierarchy)
  local base_score=0
  if [[ "$type" =~ opus ]]; then
    base_score=3000
  elif [[ "$type" =~ sonnet ]]; then
    base_score=2000  
  elif [[ "$type" =~ haiku ]]; then
    base_score=1000
  else
    # Unknown type - skip it
    echo "0"
    return
  fi
  
  # Version scoring (newer versions get higher scores)
  local version_score
  version_score=$(version_to_numeric "$version")
  
  # Date scoring (newer dates get bonus points)
  local date_score=0
  if [[ "$date" =~ ^[0-9]{8}$ ]] && [ "$date" -gt "20230000" ]; then
    # Convert YYYYMMDD to a score (more recent = higher)
    date_score=$((date - 20230000))
  fi
  
  # Variant scoring (v2 > v1 > no variant)
  local variant_score=0
  case "$variant" in
    "v2") variant_score=20 ;;
    "v1") variant_score=10 ;;
  esac
  
  # Context length penalty (limited context is less flexible)
  local context_penalty=0
  if [ -n "$context" ]; then
    local context_num="${context%k}"
    if [ "$context_num" -lt 200 ]; then
      context_penalty=50
    elif [ "$context_num" -lt 500 ]; then
      context_penalty=20
    fi
  fi
  
  # Inference profile bonus (recommended approach)
  local profile_bonus=0
  if [[ "$model_id" =~ inference-profile ]]; then
    profile_bonus=100
  fi
  
  local final_score=$((base_score + version_score + date_score + variant_score + profile_bonus - context_penalty))
  echo "$final_score"
}

is_fast_model() {
  local model_id="$1"
  [[ "$model_id" =~ haiku ]] || [[ "$model_id" =~ instant ]]
}

test_model_access() {
  local region="$1"
  local model_or_profile="$2"
  local quiet="${3:-false}"
  
  if [ "$quiet" != true ]; then
    log_info "  Testing access to: $model_or_profile"
  fi
  
  local temp_response="/tmp/bedrock_test_$$"
  local temp_error="/tmp/bedrock_error_$$"
  
  # Cleanup function for temporary files
  cleanup_temp_files() {
    rm -f "$temp_response" "$temp_error"
  }
  
  # Set trap to ensure cleanup on script exit
  trap cleanup_temp_files EXIT
  
  if aws bedrock-runtime invoke-model \
    --region "$region" \
    --cli-binary-format raw-in-base64-out \
    --model-id "$model_or_profile" \
    --content-type "application/json" \
    --accept "application/json" \
    --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}' \
    "$temp_response" 2>"$temp_error"; then
    
    if [ -f "$temp_response" ] && jq -e '.content[0].text' "$temp_response" >/dev/null 2>&1; then
      local response_text
      response_text=$(jq -r '.content[0].text' "$temp_response")
      if [ "$quiet" != true ]; then
        log_success "    ✅ Working (response: \"$response_text\")"
      fi
      cleanup_temp_files
      return 0
    else
      if [ "$quiet" != true ]; then
        log_warning "    ❌ Invalid response format"
        if [ -f "$temp_response" ]; then
          log_info "    Response: $(cat "$temp_response")"
        fi
      fi
    fi
  else
    if [ "$quiet" != true ]; then
      log_warning "    ❌ Failed to access"
      if [ -f "$temp_error" ] && [ -s "$temp_error" ]; then
        local error_msg
        error_msg=$(head -1 "$temp_error")
        log_info "    Error: $error_msg"
      fi
    fi
  fi
  
  cleanup_temp_files
  return 1
}

discover_all_models() {
  local region="$1"
  local dry_run="${2:-false}"
  
  log_info "🔍 Discovering all available Claude models..."
  
  declare -A all_models
  declare -A working_models
  declare -A failed_models
  
  # Collect inference profiles first (recommended approach)
  local profiles
  if profiles=$(list_inference_profiles "$region" 2>/dev/null) && [ -n "$profiles" ]; then
    log_info "  📋 Found inference profiles (recommended approach):"
    
    while read -r profile; do
      if [ -z "$profile" ]; then continue; fi
      
      local score
      score=$(score_claude_model "$profile")
      all_models["$profile"]="$score|profile"
      
      if [ "$dry_run" = true ]; then
        local parsed
        parsed=$(parse_claude_model "$profile")
        IFS='|' read -r type version date variant context <<< "$parsed"
        log_info "    📝 $profile"
        log_info "        Type: $type, Version: $version, Date: $date, Variant: $variant"
        log_info "        Score: $score"
      fi
      
      if test_model_access "$region" "$profile"; then
        working_models["$profile"]="$score|profile"
        if [ "$dry_run" = true ]; then
          log_success "        ✅ Available"
        fi
      else
        failed_models["$profile"]="$score|profile"
        if [ "$dry_run" = true ]; then
          log_warning "        ❌ Not accessible"
        fi
      fi
    done <<< "$profiles"
  fi
  
  # Collect direct model access
  log_info "  🧠 Checking direct model access:"
  local models
  models=$(list_claude_models "$region")
  
  while read -r model; do
    if [ -z "$model" ]; then continue; fi
    
    # Skip if already tested as inference profile
    if [[ -v all_models["$model"] ]]; then continue; fi
    
    local score
    score=$(score_claude_model "$model")
    all_models["$model"]="$score|direct"
    
    if [ "$dry_run" = true ]; then
      local parsed
      parsed=$(parse_claude_model "$model")
      IFS='|' read -r type version date variant context <<< "$parsed"
      log_info "    📝 $model"
      log_info "        Type: $type, Version: $version, Date: $date, Variant: $variant"
      log_info "        Score: $score"
    fi
    
    if test_model_access "$region" "$model"; then
      working_models["$model"]="$score|direct"
      if [ "$dry_run" = true ]; then
        log_success "        ✅ Available"
      fi
    else
      failed_models["$model"]="$score|direct"
      if [ "$dry_run" = true ]; then
        log_warning "        ❌ Not accessible"
      fi
    fi
  done <<< "$models"
  
  if [ "$dry_run" = true ]; then
    echo ""
    log_info "📊 Summary:"
    log_info "  Total models found: ${#all_models[@]}"
    log_info "  Working models: ${#working_models[@]}"
    log_info "  Failed models: ${#failed_models[@]}"
    echo ""
  fi
  
  # Find best models from working set
  local best_main="" best_fast="" best_score=0 best_fast_score=0
  
  for model in "${!working_models[@]}"; do
    local score_info="${working_models[$model]}"
    local score="${score_info%%|*}"
    
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
  done
  
  # Use main model for fast if no dedicated fast model found
  if [ -z "$best_fast" ]; then
    best_fast="$best_main"
  fi
  
  if [ -n "$best_main" ]; then
    if [ "$dry_run" = true ]; then
      log_success "🎯 Recommended configuration:"
      log_info "  🧠 Main model: $best_main (score: $best_score)"
      log_info "  ⚡ Fast model: $best_fast"
      echo ""
      log_info "💡 To apply this configuration, run without --dry-run"
      return 0
    else
      echo "$best_main|$best_fast"
      return 0
    fi
  fi
  
  log_error "❌ No working Claude models found"
  return 1
}

find_best_models() {
  local region="$1"
  discover_all_models "$region" false
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
  
  # Set environment variables via claude config with error handling
  local config_errors=()
  
  if ! claude config set --global env.CLAUDE_CODE_USE_BEDROCK "1" >/dev/null 2>&1; then
    config_errors+=("Failed to set CLAUDE_CODE_USE_BEDROCK")
  fi
  
  if ! claude config set --global env.AWS_REGION "$region" >/dev/null 2>&1; then
    config_errors+=("Failed to set AWS_REGION")
  fi
  
  if ! claude config set --global env.ANTHROPIC_MODEL "$main_model" >/dev/null 2>&1; then
    config_errors+=("Failed to set ANTHROPIC_MODEL")
  fi
  
  if ! claude config set --global env.ANTHROPIC_SMALL_FAST_MODEL "$fast_model" >/dev/null 2>&1; then
    config_errors+=("Failed to set ANTHROPIC_SMALL_FAST_MODEL")
  fi
  
  if ! claude config set --global env.ANTHROPIC_SMALL_FAST_MODEL_AWS_REGION "$region" >/dev/null 2>&1; then
    config_errors+=("Failed to set ANTHROPIC_SMALL_FAST_MODEL_AWS_REGION")
  fi
  
  if [ ${#config_errors[@]} -gt 0 ]; then
    log_error "❌ Configuration failed with errors:"
    for error in "${config_errors[@]}"; do
      log_error "  - $error"
    done
    
    # Restore backup if configuration failed
    if [ -n "$backup_file" ]; then
      restore_claude_config "$backup_file"
    fi
    return 1
  fi
  
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
usage() {
  cat << EOF
Usage: $0 [OPTIONS]

Configure Claude Code to use Amazon Bedrock with dynamic model discovery.

OPTIONS:
    -d, --dry-run       Show available models without making changes
    -h, --help          Show this help message
    
EXAMPLES:
    $0                  Configure Claude with best available models
    $0 --dry-run        List all available models and recommended configuration
EOF
}

main() {
  local dry_run=false
  
  # Parse command line arguments
  while [[ $# -gt 0 ]]; do
    case $1 in
      -d|--dry-run)
        dry_run=true
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        log_error "Unknown option: $1"
        usage
        exit 1
        ;;
    esac
  done
  
  if [ "$dry_run" = true ]; then
    log_info "🔍 Dry-run mode: Discovering available models without making changes"
  else
    log_info "🚀 Configuring Claude Code to use Amazon Bedrock"
  fi
  echo ""
  
  # Load environment if available (non-fatal)
  load_environment 2>/dev/null || true
  
  # Check prerequisites
  check_bedrock_prereqs
  
  # Setup region and verify Bedrock access
  local region
  region=$(get_bedrock_region)
  verify_bedrock_access "$region"
  
  # Handle dry-run mode
  if [ "$dry_run" = true ]; then
    discover_all_models "$region" true
    exit 0
  fi
  
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
  
  # Confirm before making changes
  if [ -t 0 ]; then  # Only prompt if running interactively
    echo ""
    log_warning "⚠️  This will modify your Claude configuration."
    log_info "Current configuration will be backed up automatically."
    echo ""
    read -p "Continue? (y/N): " -r
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      log_info "❌ Configuration cancelled by user"
      exit 0
    fi
    echo ""
  fi
  
  # Configure Claude with error handling
  local backup_file
  if ! backup_file=$(configure_claude_for_bedrock "$region" "$main_model" "$fast_model"); then
    log_error "❌ Configuration failed - no changes were made"
    exit 1
  fi
  
  # Test configuration with timeout and retries
  local test_attempts=3
  local test_passed=false
  
  for ((i=1; i<=test_attempts; i++)); do
    log_info "🧪 Testing configuration (attempt $i/$test_attempts)..."
    
    if test_claude_with_bedrock; then
      test_passed=true
      break
    else
      if [ $i -lt $test_attempts ]; then
        log_warning "⏳ Test failed, retrying in 2 seconds..."
        sleep 2
      fi
    fi
  done
  
  if [ "$test_passed" = true ]; then
    # Clean up backup on success
    if [ -n "$backup_file" ] && [ -f "$backup_file" ]; then
      rm -f "$backup_file"
    fi
    
    echo ""
    log_success "🎉 Setup complete!"
    log_info "  💡 You can now use Claude with Bedrock"
    log_info "  🔧 Verify with: claude config get --global env"
    log_info "  🗣️  Start REPL: claude"
    log_info "  🔄 To reconfigure: $0 --dry-run (then run without --dry-run)"
  else
    log_error "❌ Setup failed after $test_attempts attempts - reverting configuration"
    restore_claude_config "$backup_file"
    echo ""
    log_info "💡 Troubleshooting:"
    log_info "  - Check AWS credentials: aws sts get-caller-identity"
    log_info "  - Verify Bedrock access: aws bedrock list-foundation-models --region $region"
    log_info "  - Try dry-run mode: $0 --dry-run"
    exit 1
  fi
}

# Run main function
main "$@"
