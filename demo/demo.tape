# Render with: vhs demo/demo.tape   (https://github.com/charmbracelet/vhs)
Output demo/demo.gif

Set Shell "bash"
Set FontSize 19
Set Width 1260
Set Height 720
Set Padding 22
Set Theme "Catppuccin Mocha"
Set WindowBar Colorful
Set TypingSpeed 40ms

Hide
Type `export PATH="$PWD/.venv/bin:$PATH" && rm -rf /tmp/demo-bundle && clear` Enter
Sleep 1s
Show

Type "# bundle an app's python wheels for an offline network, with checksums"
Enter
Sleep 900ms
Type "kit bundle --skip-docker --skip-models --packages rich --output-dir /tmp/demo-bundle"
Enter
Sleep 9s
Type "# verify the bundle is intact before you carry it on-site:"
Enter
Sleep 800ms
Type "kit manifest --check --bundle-dir /tmp/demo-bundle"
Enter
Sleep 3s
Type "# now simulate a corrupted transfer and check again:"
Enter
Sleep 800ms
Type `F=$(ls /tmp/demo-bundle/wheels/*.whl | head -1); printf x >> "$F"; kit manifest --check --bundle-dir /tmp/demo-bundle`
Enter
Sleep 4s
