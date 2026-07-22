import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# 1. Load variables from the .env file
load_dotenv()

try:
    # 2. Establish connection using os.getenv()
    connection = mysql.connector.connect(
        host=os.getenv('MYSQL_HOST'),
        user=os.getenv('MYSQL_USER'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('MYSQL_DATABASE'),
        port=int(os.getenv('DB_PORT', 3307))  # cast port to an integer
    )

    if connection.is_connected():
        print("Securely connected to the database!")
        cursor = connection.cursor()
        
        cursor.execute("SELECT * FROM customers LIMIT 5")
        myresult = cursor.fetchall()
        print(myresult)

        
except Error as e:
    print(f"Database connection error: {e}")

finally:
    if 'connection' in locals() and connection.is_connected():
        cursor.close()
        connection.close()
        print("Connection closed.")