"""EcoCart entry point:  python app.py   (or: flask --app app run)"""
import os

from ecocart import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=port, debug=debug)
