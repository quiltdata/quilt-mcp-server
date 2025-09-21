#!/bin/bash
# Common logging functions for scripts

log_info() {
    echo "$1"
}

log_error() {
    echo "$1" >&2
}

log_success() {
    echo "$1"
}