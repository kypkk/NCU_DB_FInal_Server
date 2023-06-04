import io
import base64
from PIL import Image
from flask import Flask, jsonify, request
from flask import Response
import pandas as pd
import os
import pymssql
import numpy as np
import mplfinance as mpf
from dotenv import load_dotenv

load_dotenv()

db_Password = os.getenv('PASSWORD')
db_settings = {
    "host": "127.0.0.1",
    "user": "SA",
    "password": db_Password,
    "database": "TutorialDB",
    "charset": "utf8"
}

def is_transaction_legal(date, buy_or_sell, stock_code, shares, price):
    try:
        date = '\'' + date +'\''
        conn = pymssql.connect(**db_settings)
        with conn.cursor() as cursor:
                command = f"select TOP(1) remain_cash as remain_cash, (select sum(buy_or_sell * shares) from stock_transactions where stock_code={stock_code}) as shares from stock_transactions order by id DESC"
                cursor.execute(command)
                remain_cash, own_shares = cursor.fetchall()[0]
                if buy_or_sell == 1:
                    if remain_cash >= price * shares:
                        return True
                elif buy_or_sell == -1:
                    if own_shares >= shares:
                        return True
                else:
                    raise Exception("buy_or_sell not 1 or -1")
                return "buy_or_sell not 1 or -1"
        conn.commit()
        conn.close()
    except Exception as e:
        raise

def get_buy_or_sell(buy_or_sell, close):
    buy_points = []
    sell_points = []
    for date, value in buy_or_sell.items():
        if value == 1:
            buy_points.append(close[date]*1.01)
            sell_points.append(np.nan)
        elif value == -1:
            sell_points.append(close[date]*0.99)
            buy_points.append(np.nan)
        else:
            sell_points.append(np.nan)
            buy_points.append(np.nan)
    return buy_points, sell_points


conn = pymssql.connect(**db_settings)
b = io.BytesIO()
app = Flask(__name__)


@app.route('/')
def index():
    return "index"


@app.route('/hello')
def hello():
    return "hello world"


@app.route('/get_stock', methods=['POST'])
def get_date():
    data = request.json
    try:
        with conn.cursor() as cursor:
            date = '\'' + data["date"] +'\''
            command = f"select * from datefind_stockcode({date})"
            cursor.execute(command)
            result = cursor.fetchall()
            result = np.array(result)

            column_names = ['Company', 'Buy_or_sell']
            result_df = pd.DataFrame(result[:,1:], columns=column_names, index=result[:,0], dtype=float)
            result_df.index.name = 'Date'
            result_df.index = pd.to_datetime(result_df.index)
            result_df = result_df.to_json(orient="columns")

            print(result_df)
            return result_df
        conn.commit()

    except Exception as e:
        print(e)
        raise

@app.route('/initial_account', methods=['POST'])
def initialize_account():
    data = request.json
    try:
        date = '\'' + data['date'] +'\''
        deposit = int(data['deposit'])
        with conn.cursor() as cursor:
            command = f"insert into stock_transactions(id, date, buy_or_sell ,remain_cash) values(0, {date}, 0,{deposit})"
            cursor.execute(command)
            print("init sucessful transaction");
        conn.commit()
        return "Init sucessful account"
    except Exception as e:
        print(e)
        raise

@app.route('/recordTransaction', methods=['POST'])
def record_transaction():
    data = request.json
    date = data['date'] 
    buy_or_sell = data['buy_or_sell']
    stock_code = data['stock_code']
    shares = data['shares']
    price = data['price']
    print(stock_code)
    stock_code = '\''+stock_code+'\''
    try:
        if not is_transaction_legal(date, buy_or_sell, stock_code, shares, price):
            raise Exception("No enough cash or shares")
        with conn.cursor() as cursor:
            date = '\'' + date +'\''
            command = f"INSERT INTO stock_transactions (id, date, stock_code, stock_price, shares, buy_or_sell, remain_cash)\
                        SELECT MAX(id) + 1, {date}, {stock_code},\
                               {price},\
                               {shares},\
                               {buy_or_sell},\
                               ((SELECT TOP(1)remain_cash FROM stock_transactions ORDER BY id DESC) +\
                                {buy_or_sell} * -1 *{price})\
                        FROM stock_transactions;"
            cursor.execute(command)
        conn.commit()
        return "Transaction successfully created"
        
    except Exception as e:
        print(e)
        raise



if __name__ == '__main__':
    app.debug = True
    app.run()
