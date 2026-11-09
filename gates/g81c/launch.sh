#!/bin/bash
# Usage: launch.sh dry|main
cd /d/Work/FYP-search/fyp/opentsense || exit 1
if [ "$1" = dry ]; then python -u gates/g81c/g81c.py gates/g81c/dry --dry > gates/g81c/dry.log 2>&1
else python -u gates/g81c/g81c.py gates/g81c/runs/main > gates/g81c/run_main.log 2>&1; fi
echo "EXIT=$?" >> gates/g81c/$([ "$1" = dry ] && echo dry || echo run_main).log
