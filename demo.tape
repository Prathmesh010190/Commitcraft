# CommitCraft demo — records demo.gif via `vhs demo.tape`.
# Uses Hide/Show to skip the model-generation wait while recording REAL cc output.

Output demo.gif

Set Shell "bash"
Set FontSize 14
Set Width 1100
Set Height 700
Set Theme "Dracula"
Set TypingSpeed 40ms
Set PlaybackSpeed 1.0

# Put the CommitCraft venv and user-local tools on PATH.
Env PATH "/home/prathmesh-kokate/Comitcraft/Commitcraft/.venv/bin:/home/prathmesh-kokate/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Jump into a pre-seeded demo repo and clear the screen.
Type "cd /tmp/cc-demo-repo"
Enter
Sleep 400ms
Type "clear"
Enter
Sleep 300ms

# Show the unstaged change.
Type "git diff --stat"
Enter
Sleep 1500ms

# Stage it.
Type "git add auth.py"
Enter
Sleep 700ms

# Run CommitCraft.
Type "cc"
Enter

# Let the spinner appear briefly (real UI).
Sleep 2500ms

# Stop recording while the cloud model generates (takes ~60s on this machine).
Hide
Sleep 75s
Show

# The suggestions table is now on screen.
Sleep 3s

# Pick suggestion #2.
Type "2"
Enter
Sleep 2500ms

# Show the resulting log.
Type "git log --oneline -2"
Enter
Sleep 3s
