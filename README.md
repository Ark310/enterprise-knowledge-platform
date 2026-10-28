# TD POC 0.11

Upgrading from v0.10? Read **UPGRADE-FROM-0.10.md** first.

Start with **docs/START-HERE.md**. Open **docs/architecture-and-tables.html** for the combined workflow/database diagram.

One machine, three Codex roles, local Qwen3-Embedding 4B, PostgreSQL + pgvector. Automatic startup scan; manual processing. Includes the approved A/B contract, original instructions and User Master regression cases. No agent SDK or separate reasoning API key.

First time, in this order:

1. Setup-LocalModel.cmd
2. Setup-VideoTools.cmd (if ffmpeg is not already available)
3. Configure-Database.cmd
4. Initialize-Database.cmd (local-file constraint migration; existing schema retained)
5. Start-POC.cmd

Inside the main console use `/pilot`, then `/process`, `/status`, `/test T02`, `/test T04`, `/test T05`, or ask Agent C a question. `/run C:\path\request.json` supports a new scoped test request.

Read **VALIDATION.md** before treating any run as verified. The package has offline/synthetic verification; native Windows, installed Codex flags, GPU/model performance and actual TD results require target-machine acceptance. Images/SNAG/legacy DOC conversion remains pending and is reported, not silently marked complete.
