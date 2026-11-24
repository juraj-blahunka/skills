# Code review: {{TITLE}}

Repository: {{REPO}}.
Review the commits {{BASE}}..{{HEAD}} (`git -C {{REPO}} log {{BASE}}..{{HEAD}}`, `git -C {{REPO}} diff {{BASE}}..{{HEAD}}`).
Intended behavior: {{INTENT}}

Read CLAUDE.md, VISION.md, the architecture doc, the code standards and the ADRs for the project's rules.
Do a thorough senior-developer review of the change, including the related code and tests it touches.
This is a read-only review: do not edit files, commit, or run destructive commands.

{{OUTPUT}}
For each finding give: severity (critical / major / minor / nit), likelihood that a real user hits it (high / medium / low), file:line, what is wrong, a concrete failure scenario, and a suggested fix.
During your final answer, Rate each issue you find from 1 to 10 on how often it would happen, and 1-10 on how bad it would be.
Distinguish verified findings from uncertainty.
End with anything you could not verify, each written as a concrete check the developer can run end to end (what to do, what to look for), since nobody else will run it.
