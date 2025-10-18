from dotenv import load_dotenv
import os

load_dotenv()

# Database settings
DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_NAME = os.environ.get('DB_NAME')
DB_PASS = os.environ.get('DB_PASS')
DB_PORT = os.environ.get('DB_PORT')


# Security settings
SECRET_KEY = os.environ.get('SECRET_KEY')
ACCESS_TOKEN_EXPIRE_MINUTES = os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES')

# VK OAuth settings
VK_CLIENT_ID = os.environ.get('VK_CLIENT_ID')
VK_CLIENT_SECRET = os.environ.get('VK_CLIENT_SECRET')
VK_REDIRECT_URI = os.environ.get('VK_REDIRECT_URI', 'http://localhost:8000/users/auth/vk/callback')
VK_API_VERSION = os.environ.get('VK_API_VERSION', '5.131')

# File upload settings
UPLOAD_DIR = os.environ.get('UPLOAD_DIR', 'uploads')
ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

DATABASE_URL = f'postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

DATE_FORMAT = '%m/%d/%Y %H:%M UTC'