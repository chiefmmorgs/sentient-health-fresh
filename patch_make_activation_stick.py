from pathlib import Path, re
p = Path("api/sentient_roma_api.py")
s = p.read_text()

# (A) Insert a Loguru monkeypatch guard (only once)
if "def _patch_loguru_level_idempotent(" not in s:
    guard = '''
# --- BEGIN loguru duplicate-level guard ---
def _patch_loguru_level_idempotent():
    try:
        from loguru._logger import Logger as _Logger
        _orig = _Logger.level
        def _safe_level(self, *a, **kw):
            try:
                return _orig(self, *a, **kw)
            except Exception as e:
                msg = str(e)
                if "already exists" in msg and a:
                    # If duplicate, just get the level info instead of failing.
                    try:
                        return _orig(self, a[0])
                    except Exception:
                        return None
                raise
        _Logger.level = _safe_level
    except Exception:
        # If loguru is not present or internals changed, carry on.
        pass

# Apply ASAP at import time
_patch_loguru_level_idempotent()
# --- END loguru duplicate-level guard ---
'''
    # put it near the top, after imports block
    s = s.replace("from fastapi.responses import JSONResponse\n", "from fastapi.responses import JSONResponse\n" + guard, 1)

# (B) Make /debug/warmup do a *real* ROMA create_with_profile and bind it.
# Replace the existing line where warmup currently calls our "create/bind once"
s = re.sub(
    r'agent = _create_and_bind_agent_once\(prof\)\n\s*agent = _finalize_agent_activation\(agent, prof\)',
    'from sentientresearchagent.framework_entry import LightweightSentientAgent as _LSA\n'
    '    try:\n'
    '        agent = _LSA.create_with_profile(profile_name=prof)\n'
    '    except Exception as _e:\n'
    '        # Fallback to previous path if ROMA throws for any reason\n'
    '        agent = _create_and_bind_agent_once(prof)\n'
    '    agent = _finalize_agent_activation(agent, prof)',
    s,
    count=1
)

# Also ensure we bind the created agent to app.state (in case earlier code didn’t)
s = re.sub(
    r'sm = getattr\(agent, "system_manager", None\)',
    'sm = getattr(agent, "system_manager", None)\n'
    '    try:\n'
    '        app.state.sentient_agent = agent\n'
    '    except Exception:\n'
    '        pass',
    s,
    count=1
)

p.write_text(s)
print("Patched", p)
