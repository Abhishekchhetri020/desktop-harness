---
name: Bug report
about: Something doesn't work as expected
labels: bug
---

**What happened**
A clear description.

**Expected behavior**
What you thought would happen.

**Repro**
```python
# Smallest snippet that reproduces it
from desktop_harness import ...
```

**Environment**
Run `desktop-harness --doctor` and paste the output.

```
desktop-harness ...
Python: ...
pyobjc: ...
  ✓/✗ accessibility: ...
  ✓/✗ screen_recording: ...
  ✓/✗ automation_system_events: ...
```

- macOS version: (`sw_vers`)
- Mac model: (Intel / Apple Silicon)
- App being driven, if relevant: (Notes 13.x, Slack 4.x, ...)

**Additional context**
Stack traces, screenshots, etc.
