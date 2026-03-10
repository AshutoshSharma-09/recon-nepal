import sys
import os

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from app import models
from app.models import Base

def init_db():
    print("Creating Cash vs AR tables...")
    # This will create tables if they don't exist.
    # It won't update existing tables (safe).
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

if __name__ == "__main__":
    init_db()
