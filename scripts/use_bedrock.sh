#!/bin/bash
# Configure Claude Code to use AWS Bedrock via the `claude` CLI (no .env edits).
# - Requires: AWS CLI, jq, and the Claude Code CLI (`claude`).
# - Behavior: Detect region, verify Bedrock access, choose best Claude models available,
#             and write settings to Claude's global config via `claude config`.
#
# References:
# * Claude Code settings & global config: https://docs.anthropic.com/en/docs/claude-code/settings
# * Claude Code on Amazon Bedrock:      https://docs.anthropic.com/en/docs/claude-code/amazon-bedrock
# * Supported Bedrock model IDs:        https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html
# * `claude config` env block behavior: https://github.com/anthropics/claude-code/issues/1737

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$REPO_ROOT/shared/common.sh"

# -----------------------------------------------------------------------------
# Model parsing and scoring functions
# -----------------------------------------------------------------------------
get_model_type_score() {
  local model_type="$1"
  case "$model_type" in
    "opus-4") echo 100 ;;
    "sonnet-4") echo 90 ;;
    "haiku-4") echo 80 ;;
    "opus-3") echo 70 ;;
    "sonnet-3-7") echo 65 ;;
    "sonnet-3-5") echo 60 ;;
    "sonnet-3") echo 50 ;;
    "haiku-3-5") echo 40 ;;
    "haiku-3") echo 30 ;;
    "instant") echo 20 ;;
    "v2") echo 10 ;;
    *) echo 0 ;;
  esac
}

is_fast_model_type() {
  local model_type="$1"
  case "$model_type" in
    "haiku-4"|"haiku-3-5"|"haiku-3"|"sonnet-3"|"instant") return 0 ;;
    *) return 1 ;;
  esac
}
parse_model_info() {
  local model_id="$1"
  
  # Extract base model name from anthropic.claude-* format
  local base_name
  base_name=$(echo "$model_id" | sed 's/^anthropic\.claude-//' | sed 's/:.*$//')
  
  # Parse different patterns
  local model_type version date
  
  if [[ "$base_name" =~ ^(opus|sonnet|haiku)-4-([0-9]+)-([0-9]{8})-v[0-9]+$ ]]; then
    # Claude 4: opus-4-1-20250805-v1, sonnet-4-20250514-v1
    model_type="${BASH_REMATCH[1]}-4"
    version="${BASH_REMATCH[2]}"
    date="${BASH_REMATCH[3]}"
  elif [[ "$base_name" =~ ^3-7-(sonnet)-([0-9]{8})-v[0-9]+$ ]]; then
    # Claude 3.7: 3-7-sonnet-20250219-v1
    model_type="sonnet-3-7"
    version="1"
    date="${BASH_REMATCH[2]}"
  elif [[ "$base_name" =~ ^3-5-(sonnet|haiku)-([0-9]{8})-v([0-9]+)$ ]]; then
    # Claude 3.5: 3-5-sonnet-20241022-v2, 3-5-haiku-20241022-v1
    model_type="${BASH_REMATCH[1]}-3-5"
    version="${BASH_REMATCH[3]}"
    date="${BASH_REMATCH[2]}"
  elif [[ "$base_name" =~ ^3-(opus|sonnet|haiku)-([0-9]{8})-v[0-9]+$ ]]; then
    # Claude 3: 3-opus-20240229-v1, 3-sonnet-20240229-v1
    model_type="${BASH_REMATCH[1]}-3"
    version="1"
    date="${BASH_REMATCH[2]}"
  elif [[ "$base_name" =~ ^(instant)-v([0-9]+)$ ]]; then
    # Claude Instant: instant-v1
    model_type="instant"
    version="${BASH_REMATCH[2]}"
    date="20230101"  # Default old date for instant
  elif [[ "$base_name" =~ ^v([0-9]+)$ ]]; then
    # Claude v2: v2, v2:1
    model_type="v2"
    version="${BASH_REMATCH[1]}"
    date="20220101"  # Default old date for v2
  else
    # Unknown format
    model_type="unknown"
    version="0"
    date="19700101"
  fi
  
  echo "$model_type|$version|$date"
}

score_model() {
  local model_info="$1"
  local model_type version date
  IFS='|' read -r model_type version date <<< "$model_info"
  
  local type_score
  type_score=$(get_model_type_score "$model_type")
  local version_score=$((version * 10))  # Higher version = better
  local date_score
  
  # Convert date to a score (more recent = higher score)
  if [[ "$date" =~ ^([0-9]{4})([0-9]{2})([0-9]{2})$ ]]; then
    local year=${BASH_REMATCH[1]}
    local month=${BASH_REMATCH[2]}
    local day=${BASH_REMATCH[3]}
    date_score=$(((year - 2020) * 10000 + month * 100 + day))
  else
    date_score=0
  fi
  
  local total_score=$((type_score * 1000000 + date_score * 100 + version_score))
  echo "$total_score"
}

sort_models_by_preference() {
  local models="$1"
  local temp_file="/tmp/model_scores_$$"
  
  # Score each model and create sortable list
  while read -r model_id; do
    local model_info
    model_info=$(parse_model_info "$model_id")
    local score
    score=$(score_model "$model_info")
    echo "$score|$model_id|$model_info"
  done <<< "$models" > "$temp_file"
  
  # Sort by score (descending) and return just the model IDs
  sort -nr "$temp_file" | cut -d'|' -f2
  rm -f "$temp_file"
}

# -----------------------------------------------------------------------------
# Guards & prerequisites
# -----------------------------------------------------------------------------
require_cmd() {
  local bin="$1"; shift
  if ! command -v "$bin" >/dev/null 2>&1; then
    log_error "Missing required command: $bin"
    case "$bin" in
      claude) log_info "Install Claude Code: https://docs.anthropic.com/en/docs/claude-code/setup";;
      aws)    log_info "Install AWS CLI:    brew install awscli";;
      jq)     log_info "Install jq:         brew install jq";;
    esac
    exit 1
  fi
}

check_prereqs() {
  log_info "Checking prerequisites..."
  require_cmd "claude"
  require_cmd "aws"
  require_cmd "jq"

  # Validate AWS identity
  if ! aws sts get-caller-identity >/dev/null 2>&1; then
    log_error "AWS credentials not configured or invalid. Run: aws configure (or SSO login)."
    exit 1
  fi
  local ident
  ident=$(aws sts get-caller-identity --output json)
  log_success "✓ AWS credentials valid"
  log_info "  Account: $(echo "$ident" | jq -r '.Account')"
  log_info "  ARN:     $(echo "$ident" | jq -r '.Arn')"
}

# -----------------------------------------------------------------------------
# Region & Bedrock access
# -----------------------------------------------------------------------------
get_aws_region() {
  local region="${AWS_REGION:-${AWS_DEFAULT_REGION:-${CDK_DEFAULT_REGION:-}}}"
  if [ -z "$region" ]; then
    region=$(aws configure get region 2>/dev/null || true)
  fi
  if [ -z "$region" ]; then
    log_warning "No AWS region configured; defaulting to us-east-1."
    region="us-east-1"
  fi
  echo "$region"
}

check_bedrock_access() {
  local region="$1"
  log_info "Checking Bedrock access in region: $region"
  local error_output
  if ! error_output=$(aws bedrock list-foundation-models --region "$region" 2>&1); then
    log_error "Cannot access Amazon Bedrock in region $region"
    log_info "Error: $error_output"
    log_info "Ensure Bedrock is enabled and you have permissions: bedrock:ListFoundationModels, bedrock:InvokeModel"
    exit 1
  fi
    log_success "✓ Bedrock access confirmed"
}

# -----------------------------------------------------------------------------
# Prerequisites and AWS region setup
# -----------------------------------------------------------------------------
require_cmd() {
}

# -----------------------------------------------------------------------------
# Model scoring and selection heuristics
# -----------------------------------------------------------------------------
score_model() {
  local model_id="$1"
  local score=0
  
  # Claude 4 models get highest priority
  if [[ "$model_id" =~ claude-opus-4 ]]; then
    score=$((score + 1000))
    # Newer versions within Claude 4
    if [[ "$model_id" =~ 20250805 ]]; then score=$((score + 100)); fi
    if [[ "$model_id" =~ 20250514 ]]; then score=$((score + 90)); fi
  elif [[ "$model_id" =~ claude-sonnet-4 ]]; then
    score=$((score + 900))
    if [[ "$model_id" =~ 20250514 ]]; then score=$((score + 100)); fi
  
  # Claude 3.7 models
  elif [[ "$model_id" =~ claude-3-7-sonnet ]]; then
    score=$((score + 800))
    if [[ "$model_id" =~ 20250219 ]]; then score=$((score + 100)); fi
  
  # Claude 3.5 models  
  elif [[ "$model_id" =~ claude-3-5-sonnet ]]; then
    score=$((score + 700))
    if [[ "$model_id" =~ 20241022-v2 ]]; then score=$((score + 100)); fi
    if [[ "$model_id" =~ 20241022 ]]; then score=$((score + 90)); fi
    if [[ "$model_id" =~ 20240620 ]]; then score=$((score + 80)); fi
  elif [[ "$model_id" =~ claude-3-5-haiku ]]; then
    score=$((score + 600))
    if [[ "$model_id" =~ 20241022 ]]; then score=$((score + 100)); fi
  
  # Claude 3 standard models
  elif [[ "$model_id" =~ claude-3-opus ]]; then
    score=$((score + 500))
    if [[ "$model_id" =~ 20240229 ]] && [[ ! "$model_id" =~ : ]]; then score=$((score + 100)); fi
  elif [[ "$model_id" =~ claude-3-sonnet ]]; then
    score=$((score + 400))
    if [[ "$model_id" =~ 20240229 ]] && [[ ! "$model_id" =~ : ]]; then score=$((score + 100)); fi
  elif [[ "$model_id" =~ claude-3-haiku ]]; then
    score=$((score + 300))
    if [[ "$model_id" =~ 20240307 ]] && [[ ! "$model_id" =~ : ]]; then score=$((score + 100)); fi
  
  # Claude 2 and older models
  elif [[ "$model_id" =~ claude-v2 ]]; then
    score=$((score + 100))
  elif [[ "$model_id" =~ claude-instant ]]; then
    score=$((score + 50))
  fi
  
  # Penalize context-limited versions (e.g., :200k, :28k)
  if [[ "$model_id" =~ :[0-9]+k ]]; then
    score=$((score - 10))
  fi
  
  echo "$score"
}

sort_models_by_preference() {
  local profiles="$1"
  
  # Create scored list: score|profile_arn|model_id
  local scored_models=""
  while IFS='|' read -r profile_arn model_id; do
    local score
    score=$(score_model "$model_id")
    scored_models="$scored_models$score|$profile_arn|$model_id"$'\n'
  done <<< "$profiles"
  
  # Sort by score (descending) and return profile_arn|model_id format
  echo "$scored_models" | sort -t'|' -k1,1nr | cut -d'|' -f2,3
}

find_working_model() {
  local region="$1"
  local profiles="$2"
  local model_type="$3"  # "main" or "fast"
  
  log_info "Finding working $model_type model..."
  
  # Sort models by preference
  local sorted_models
  sorted_models=$(sort_models_by_preference "$profiles")
  
  # For fast models, prefer Haiku models
  if [ "$model_type" = "fast" ]; then
    # Try Haiku models first
    while IFS='|' read -r profile_arn model_id; do
      if [[ "$model_id" =~ haiku ]]; then
        log_info "Testing Haiku model: $model_id"
        if validate_model_access "$region" "$profile_arn" "profile"; then
          echo "$profile_arn|profile"
          return 0
        fi
      fi
    done <<< "$sorted_models"
  fi
  
  # Try all models in preference order
  while IFS='|' read -r profile_arn model_id; do
    log_info "Testing model: $model_id (score: $(score_model "$model_id"))"
    if validate_model_access "$region" "$profile_arn" "profile"; then
      echo "$profile_arn|profile"
      return 0
    fi
  done <<< "$sorted_models"
  
  log_error "No working $model_type models found"
  return 1
}
# -----------------------------------------------------------------------------
# Discover available models and inference profiles
# -----------------------------------------------------------------------------
list_available_claude_models() {
  local region="$1"
  aws bedrock list-foundation-models \
    --region "$region" \
    --output json | jq -r '.modelSummaries[] | select(.providerName=="Anthropic") | .modelId' | sort
}

list_inference_profiles() {
  local region="$1"
  
  # List inference profiles and extract those with Claude models (send debug to stderr)
  local profiles
  if profiles=$(aws bedrock list-inference-profiles --region "$region" --output json 2>/dev/null); then
    echo "$profiles" | jq -r '.inferenceProfileSummaries[] | select(.models[]?.modelArn | contains("claude")) | .inferenceProfileArn + "|" + (.models[0].modelArn | split("/")[-1])' | sort -u
  else
    return 1
  fi
}

# -----------------------------------------------------------------------------
# Validate model/profile access by making a test call
# -----------------------------------------------------------------------------
validate_model_access() {
  local region="$1"; local model_or_profile="$2"; local access_type="$3"
  
  if [ "$access_type" = "profile" ]; then
    log_info "Validating inference profile: $model_or_profile"
  else
    log_info "Validating direct model access: $model_or_profile"
  fi
  
  # Test the model/profile with a simple call
  local response
  if ! response=$(aws bedrock-runtime invoke-model \
    --region "$region" \
    --cli-binary-format raw-in-base64-out \
    --model-id "$model_or_profile" \
    --content-type "application/json" \
    --accept "application/json" \
    --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}' \
    /tmp/bedrock-test-response.json 2>&1); then
    
    # Check if it's an inference profile issue
    if echo "$response" | grep -q "inference profile"; then
      log_warning "Model $model_or_profile requires inference profile setup"
    else
      log_warning "Cannot invoke $model_or_profile: $response"
    fi
    rm -f /tmp/bedrock-test-response.json
    return 1
  fi
  
  # Check if we got a valid response
  if [ -f /tmp/bedrock-test-response.json ]; then
    if jq -e '.content[0].text' /tmp/bedrock-test-response.json >/dev/null 2>&1; then
      local response_text
      response_text=$(jq -r '.content[0].text' /tmp/bedrock-test-response.json)
      if [ "$access_type" = "profile" ]; then
        log_success "✓ Inference profile working (response: \"$response_text\")"
      else
        log_success "✓ Direct model access working (response: \"$response_text\")"
      fi
      rm -f /tmp/bedrock-test-response.json
      return 0
    else
      log_error "Invalid response format from $model_or_profile"
      cat /tmp/bedrock-test-response.json
      rm -f /tmp/bedrock-test-response.json
      return 1
    fi
  else
    log_error "No response file created for $model_or_profile"
    return 1
  fi
}

# -----------------------------------------------------------------------------
# Model selection with dynamic preferences
# -----------------------------------------------------------------------------
get_best_model_or_profile() {
  local region="$1"
  local available_models="$2"
  
  # Get inference profiles and use them exclusively
  local profiles
  if profiles=$(list_inference_profiles "$region" 2>/dev/null); then
    log_info "Available inference profiles:" >&2
    while IFS='|' read -r profile_arn model_id; do
      log_info "  - Profile: $profile_arn (Model: $model_id)" >&2
    done <<< "$profiles"
    
    # Extract just the model IDs and sort them by preference
    local model_ids
    model_ids=$(echo "$profiles" | cut -d'|' -f2)
    local sorted_models
    sorted_models=$(sort_models_by_preference "$model_ids")
    
    log_info "Models sorted by preference:" >&2
    while read -r model_id; do
      local model_info
      model_info=$(parse_model_info "$model_id")
      local score
      score=$(score_model "$model_info")
      log_info "  - $model_id (score: $score, info: $model_info)" >&2
    done <<< "$sorted_models"
    
    # Find the profile ARN for the top-ranked model
    local best_model
    best_model=$(echo "$sorted_models" | head -1)
    
    local best_profile_arn
    while IFS='|' read -r profile_arn model_id; do
      if [[ "$model_id" == "$best_model" ]]; then
        best_profile_arn="$profile_arn"
        break
      fi
    done <<< "$profiles"
    
    if [ -n "$best_profile_arn" ]; then
      echo "$best_profile_arn|profile"
      return 0
    fi
  fi
  
  # If no inference profiles available, fail
  log_error "No inference profiles available. This script requires inference profile support." >&2
  return 1
}

get_best_fast_model_profile() {
  local region="$1"
  
  local profiles
  if profiles=$(list_inference_profiles "$region" 2>/dev/null); then
    # Extract model IDs and find fast models
    local model_ids
    model_ids=$(echo "$profiles" | cut -d'|' -f2)
    
    # Filter for fast model types and sort
    local fast_candidates=""
    while read -r model_id; do
      local model_info
      model_info=$(parse_model_info "$model_id")
      local model_type
      model_type=$(echo "$model_info" | cut -d'|' -f1)
      
      if is_fast_model_type "$model_type"; then
        fast_candidates+="$model_id"$'\n'
      fi
    done <<< "$model_ids"
    
    if [ -n "$fast_candidates" ]; then
      local best_fast_model
      best_fast_model=$(sort_models_by_preference "$fast_candidates" | head -1)
      
      # Find the profile ARN for this model
      local fast_profile_arn
      while IFS='|' read -r profile_arn model_id; do
        if [[ "$model_id" == "$best_fast_model" ]]; then
          fast_profile_arn="$profile_arn"
          break
        fi
      done <<< "$profiles"
      
      if [ -n "$fast_profile_arn" ]; then
        echo "$fast_profile_arn|profile"
        return 0
      fi
    fi
  fi
  
  return 1
}

# -----------------------------------------------------------------------------
# Configuration backup and validation
# -----------------------------------------------------------------------------
backup_claude_config() {
  local backup_file="/tmp/claude_settings_backup_$(date +%Y%m%d_%H%M%S).json"
  if [ -f ~/.claude/settings.json ]; then
    cp ~/.claude/settings.json "$backup_file"
    echo "$backup_file"
  else
    echo ""
  fi
}

restore_claude_config() {
  local backup_file="$1"
  if [ -n "$backup_file" ] && [ -f "$backup_file" ]; then
    log_info "Restoring Claude configuration from backup..."
    cp "$backup_file" ~/.claude/settings.json
    rm -f "$backup_file"
    log_success "✓ Configuration restored"
  fi
}

test_claude_cli() {
  local expected_model="$1"
  log_info "Testing Claude CLI with new configuration..."
  
  # Test basic Claude CLI functionality with --print for non-interactive mode
  local test_response
  if ! test_response=$(timeout 30 claude --print "Say 'Hello from Bedrock' in exactly those words" 2>&1); then
    log_error "Claude CLI test failed: $test_response"
    return 1
  fi
  
  # Check if response contains expected content
  if echo "$test_response" | grep -q "Hello from Bedrock"; then
    log_success "✓ Claude CLI is working with Bedrock configuration"
    log_info "Response: $(echo "$test_response" | head -1)"
    return 0
  else
    log_error "Claude CLI response unexpected: $test_response"
    return 1
  fi
}

# -----------------------------------------------------------------------------
# Write to Claude global config via `claude config`
# -----------------------------------------------------------------------------
# We maintain the `env` object inside ~/.claude/settings.json and merge keys.
# `claude config get --global env` returns JSON; we merge and set it back.

claude_config_set_env() {
  local key="$1"; local value="$2"
  local current
  if ! current=$(claude config get --global env 2>/dev/null); then
    current='{}'
  fi
  # Normalize empty
  if [ -z "$current" ] || [ "$current" = "null" ]; then current='{}'; fi
  local updated
  updated=$(jq --arg k "$key" --arg v "$value" '. as $cfg | ($cfg // {}) | .[$k]=$v' <<<"$current")
  claude config set --global env "$updated" >/dev/null
}

apply_bedrock_settings() {
  local region="$1"; local model="$2"; local fast_model="$3"
  log_info "Applying global Claude settings for Bedrock..."
  claude_config_set_env "CLAUDE_CODE_USE_BEDROCK" "1"
  claude_config_set_env "AWS_REGION" "$region"
  claude_config_set_env "ANTHROPIC_MODEL" "$model"
  claude_config_set_env "ANTHROPIC_SMALL_FAST_MODEL" "$fast_model"
  claude_config_set_env "ANTHROPIC_SMALL_FAST_MODEL_AWS_REGION" "$region"
  log_success "✓ Wrote Bedrock configuration to ~/.claude/settings.json"
  
  # Debug: show what we actually configured
  log_info "Configuration applied:"
  log_info "  ANTHROPIC_MODEL: $model"
  log_info "  ANTHROPIC_SMALL_FAST_MODEL: $fast_model"
}

show_summary() {
  local region="$1"; local model="$2"; local fast="$3"
  log_success ""
  log_success "🎉 Bedrock configuration complete (via claude CLI)"
  log_info    "  Region:      $region"
  log_info    "  Main model:  $model"
  log_info    "  Fast model:  $fast"
  log_info    ""
  log_info    "Verify with:   claude config get --global env"
  log_info    "Start REPL:    claude  (then run /config to inspect)"
}

main() {
  log_info "=== Configure Claude Code to use Amazon Bedrock (global) ==="
  
  # Load environment variables first
  load_environment
  
  check_prereqs

  local region
  region=$(get_aws_region)
  check_bedrock_access "$region"

  local available
  available=$(list_available_claude_models "$region")
  if [ -z "$available" ]; then
    log_error "No Anthropic Claude models available in $region"
    exit 1
  fi
  log_info "Available Claude models in $region:"; while read -r m; do echo "  - $m"; done <<<"$available"

  # Get the best model or inference profile
  log_info "Finding best available inference profile..."
  local main_selection
  if ! main_selection=$(get_best_model_or_profile "$region" "$available"); then
    log_error "No suitable inference profiles found"
    exit 1
  fi
  
  local main="${main_selection%%|*}"
  local main_type="${main_selection##*|}"
  
  if [ -z "$main" ]; then
    log_error "Could not find any suitable Claude inference profile"
    exit 1
  fi
  
  log_info "Selected main: $main (via $main_type)"

  # For fast model, try to find a suitable fast model profile
  local fast="$main"
  local fast_type="$main_type"
  
  log_info "Finding best fast model inference profile..."
  local fast_selection
  if fast_selection=$(get_best_fast_model_profile "$region"); then
    fast="${fast_selection%%|*}"
    fast_type="${fast_selection##*|}"
    log_info "Found fast model profile: $fast"
  else
    log_info "No dedicated fast model profile found, using main model for both"
  fi

  # Validate that we can actually use the selected main model/profile
  log_info "Testing main model/profile access..."
  if ! validate_model_access "$region" "$main" "$main_type"; then
    log_error "Cannot access selected model/profile: $main"
    exit 1
  fi
  
  # Validate fast model if different from main
  if [ "$fast" != "$main" ]; then
    log_info "Testing fast model/profile access..."
    if ! validate_model_access "$region" "$fast" "$fast_type"; then
      log_warning "Cannot access fast model/profile, using main for both"
      fast="$main"
      fast_type="$main_type"
    fi
  fi

  log_info "Final selection:"
  log_info "  Main: $main ($main_type)"
  log_info "  Fast: $fast ($fast_type)"

  # Backup current configuration before making changes
  local backup_file
  backup_file=$(backup_claude_config)
  if [ -n "$backup_file" ]; then
    log_info "Created configuration backup: $backup_file"
  fi

  # Apply new configuration
  apply_bedrock_settings "$region" "$main" "$fast"
  
  # Test the configuration
  if test_claude_cli "$main"; then
    log_success "✓ Claude CLI configuration validated successfully"
    # Clean up backup on success
    if [ -n "$backup_file" ]; then
      rm -f "$backup_file"
    fi
    show_summary "$region" "$main" "$fast"
  else
    log_error "❌ Claude CLI test failed - reverting configuration"
    restore_claude_config "$backup_file"
    exit 1
  fi
}

main "$@"
