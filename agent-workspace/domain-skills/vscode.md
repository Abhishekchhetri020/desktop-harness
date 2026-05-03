# VS Code skill

VS Code is Electron — its AX tree is sparse (mostly window chrome). Drive it
via the **command palette** (`cmd+shift+p`) which exposes every action.

## Open a file

```python
activate("Visual Studio Code")
key("cmd+p")              # Quick Open
type_text("desktop_harness/cli.py")
key("return")
```

## Run any command

```python
key("cmd+shift+p")
type_text("Format Document")
key("return")
```

## Multi-cursor edit, save, close

```python
key("cmd+a"); key("cmd+c")    # select all + copy
key("cmd+s")                  # save
key("cmd+w")                  # close tab
```

## Open a file via CLI (preferred — no UI driving needed)

```python
import subprocess
subprocess.run(["code", "/path/to/file.py"], check=False)
```

## Switch the integrated terminal

```python
key("ctrl+`")
```

## Install an extension

```python
import subprocess
subprocess.run(["code", "--install-extension", "ms-python.python"], check=False)
```
