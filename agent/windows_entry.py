"""Frozen entrypoint: console diagnostics or Windows SCM dispatcher."""
import sys
if __name__=='__main__':
    if '--service' in sys.argv:
        from agent.windows_service import dispatch
        dispatch()
    else:
        from agent.main import run
        run()
