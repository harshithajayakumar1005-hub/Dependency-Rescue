import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    DATABASE = os.path.join(BASE_DIR, 'dependency_rescue.db')
    DEBUG = True

