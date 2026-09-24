#!/bin/bash
# SkillBridge Web 启动脚本
cd /home/panjinhui/code/SkillBridge
export PATH="$HOME/.local/bin:$PATH"
export HF_HUB_OFFLINE=1
exec uv run uvicorn webapp.server:app --host 127.0.0.1 --port 8100
