"""
Run this file to start EduHub locally on your computer.
Double-click it or run: python run.py
Then open your browser and go to: http://localhost:5000
"""
import os
from app import app, init_db

if __name__ == "__main__":
    os.makedirs("uploads", exist_ok=True)
    init_db()
    print("\n" + "="*50)
    print("  EduHub is running!")
    print("  Open your browser and go to:")
    print("  http://localhost:5000")
    print("  Admin login: http://localhost:5000/admin")
    print("="*50 + "\n")
    app.run(debug=True, port=5000)
