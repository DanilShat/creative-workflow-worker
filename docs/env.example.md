# Environment examples

## Worker `.env`
```env
## Find the operator LAN IP on Windows with:
##   ipconfig | findstr IPv4
SERVER_BASE_URL=http://192.168.1.10:8000
WORKER_ID=designer-laptop-01
WORKER_TOKEN=paste-generated-token-here
WORKER_TEMP_ROOT=./runtime_data/temp
PLAYWRIGHT_PROFILE_ROOT=./runtime_data/profiles
WORKER_CAPABILITIES=browser.playwright,browser.gemini,browser.freepik,agent.chat

# Local agent routing. These use subscription CLI logins on this laptop, not API keys.
# Ollama runs on the operator laptop, not on designer workers.
CLAUDE_CLI_EXECUTABLE=claude
CODEX_CLI_EXECUTABLE=codex
CLAUDE_CLI_STATUS_ARGS=auth status
CODEX_CLI_STATUS_ARGS=login status
CLAUDE_CLI_CHAT_ARGS=--print --permission-mode dontAsk
CODEX_CLI_CHAT_ARGS=exec --ask-for-approval never --sandbox read-only -
```
