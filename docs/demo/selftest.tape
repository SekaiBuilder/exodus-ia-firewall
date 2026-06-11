# Demo: the built-in self-test - every detector kind on synthetic data.
# Regenerate from this directory:  vhs selftest.tape
# Needs: vhs (https://github.com/charmbracelet/vhs) and the repo venv installed (.venv).

Output ../assets/demo-selftest.gif

Set Shell "bash"
Set FontSize 15
Set Width 1280
Set Height 880
Set Padding 16
Set Theme "Catppuccin Mocha"
Set TypingSpeed 30ms

Hide
Type `export PATH="$PWD/../../.venv/bin:$PATH"`
Enter
Type "clear"
Enter
Show

Type "exodus selftest"
Enter
Sleep 9s
