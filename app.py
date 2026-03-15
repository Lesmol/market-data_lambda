import os
import time
import requests
import boto3
from datetime import datetime, timedelta

POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY")
EMAIL_API_KEY = os.environ.get("EMAIL_API_KEY")
EMAIL_API_ENDPOINT = os.environ.get("EMAIL_API_ENDPOINT")
CONFIG_TABLE = os.environ.get("CONFIG_TABLE")

dynamodb = boto3.resource("dynamodb")


def get_current_market_date():
    date = datetime.now() - timedelta(days=1)
    if date.weekday() == 5:
        return date - timedelta(days=1)
    if date.weekday() == 6:
        return date - timedelta(days=2)
    return date


def get_past_market_date():
    date = datetime.now() - timedelta(days=30)
    if date.weekday() == 5:
        return date - timedelta(days=1)
    if date.weekday() == 6:
        return date - timedelta(days=2)
    return date


def get_values_from_db(key_name):
    table = dynamodb.Table(CONFIG_TABLE)
    try:
        response = table.get_item(Key={'id': key_name})
        return response.get('Item', {}).get('values', [])
    except Exception as e:
        print(f"Error fetching {key_name} from DynamoDB: {e}")
        return []


def handler(event, context):
    current_date_str = get_current_market_date().strftime("%Y-%m-%d")
    past_date_str = get_past_market_date().strftime("%Y-%m-%d")
    tickers = get_values_from_db("tickers")
    recipients = get_values_from_db("email_subscribers")
    stock_data_list = []
    api_call_count = 0

    if not tickers or not recipients:
        print("Missing tickers or recipients. Check DynamoDB configuration.")
        return {"status": "error", "message": "Configuration not found"}

    try:
        for ticker in tickers:
            if api_call_count != 0 and api_call_count % 4 == 0:
                time.sleep(60)

            curr_resp = requests.get(
                f"https://api.polygon.io/v1/open-close/{ticker}/{current_date_str}?apiKey={POLYGON_API_KEY}").json()
            past_resp = requests.get(
                f"https://api.polygon.io/v1/open-close/{ticker}/{past_date_str}?apiKey={POLYGON_API_KEY}").json()

            curr_open = float(curr_resp["open"])
            past_open = float(past_resp["open"])
            perc_diff = round(((curr_open - past_open) / past_open) * 100, 2)

            stock_data_list.append({
                "symbol": ticker,
                "open": str(curr_open),
                "pastOpen": str(past_open),
                "percentageDifference": str(perc_diff)
            })
            api_call_count += 2

        forex_url = f"https://api.polygon.io/v2/aggs/ticker/C:USDZAR/range/1/day/{current_date_str}/{current_date_str}?apiKey={POLYGON_API_KEY}"
        forex_resp = requests.get(forex_url).json()

        payload = {
            "stocks": stock_data_list,
            "forex": {
                "ticker": forex_resp["ticker"].replace("C:", ""),
                "openingPrice": forex_resp["results"][0]["o"]
            },
            "recipients": recipients
        }

        headers = {
            "Content-Type": "application/json",
            "x-api-key": EMAIL_API_KEY
        }
        response = requests.post(url=EMAIL_API_ENDPOINT, json=payload, headers=headers)
        response.raise_for_status()

        return {"status": "success", "message": "Email request sent to API"}

    except Exception as e:
        print(f"Error: {str(e)}")
        raise e
