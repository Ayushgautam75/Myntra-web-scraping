from pymongo import MongoClient
from pymongo.server_api import ServerApi

uri = "mongodb+srv://ayushbro779_db_user:Ayush7505@cluster1.x0jvwif.mongodb.net/?retryWrites=true&w=majority&appName=Cluster1"

client = MongoClient(uri, server_api=ServerApi('1'))

try:
    client.admin.command('ping')
    print("MongoDB Connected Successfully")
except Exception as e:
    print("Connection Error:", e)