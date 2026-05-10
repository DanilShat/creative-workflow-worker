# Contributing

This is a personal pet project. Issues are welcome, especially if they include
clear reproduction steps, screenshots, or logs.

Pull requests are reviewed case by case. Keep changes focused, avoid committing
worker tokens, local `.env.*` files, browser profiles, or downloaded artifacts,
and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tasks.ps1 -Task test
```
