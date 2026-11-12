"""Frozen entrypoint: console diagnostics or Windows SCM dispatcher."""
import sys
if __name__=='__main__':
    if '--apply-update' in sys.argv:
        from agent.updater import apply_update_cli
        apply_update_cli()
    elif '--install-user' in sys.argv:
        from agent.user_startup import install_cli
        install_cli()
    elif '--service' in sys.argv:
        from agent.windows_service import dispatch
        dispatch()
    else:
        from agent.main import run
        run()
