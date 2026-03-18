"""
OAE Crystal Editor — Standalone Dash app.

Usage:
    python3 -m agent_v.editor --port 8052
    python3 -m agent_v.editor --cif data/exports/structure.cif
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="OAE Crystal Structure Editor"
    )
    parser.add_argument("--port", type=int, default=8052,
                        help="Port for the editor (default: 8052)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Host (default: 127.0.0.1)")
    parser.add_argument("--cif", default=None,
                        help="Path to CIF file to load on start")
    parser.add_argument("--debug", action="store_true",
                        help="Enable Dash debug mode")
    args = parser.parse_args()

    try:
        from dash import Dash
    except ImportError:
        print("ERROR: dash is required. Install with: pip install dash")
        return 1

    from agent_v.editor.editor_layout import create_editor_layout
    from agent_v.editor.editor_callbacks import register_callbacks

    app = Dash(__name__, suppress_callback_exceptions=True)
    app.title = "OAE Crystal Editor"
    app.layout = create_editor_layout()
    register_callbacks(app)

    # If a CIF file was provided, we can't easily pre-load it into dcc.Store
    # before the app starts. Print a note for the user.
    if args.cif:
        print(f"  Tip: Use the 'Import CIF' button to load {args.cif}")

    print(f"  OAE Crystal Editor running at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
