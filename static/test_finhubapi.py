import finnhub

# 1. Setup the API client with your key
API_KEY = 'd9mjup1r01qtdq8u4hu0d9mjup1r01qtdq8u4hug'
finnhub_client = finnhub.Client(api_key=API_KEY)

try:
    # 2. Request a real-time quote for Apple (AAPL)
    quote = finnhub_client.quote('AAPL')
    
    # 3. Print the results if successful
    print("✅ Connection successful!")
    print(f"Current Price (c): ${quote['c']}")
    print(f"High Price of the day (h): ${quote['h']}")
    print(f"Low Price of the day (l): ${quote['l']}")
    print(f"Previous Close Price (pc): ${quote['pc']}")

except Exception as e:
    print("❌ Connection failed!")
    print(f"Error details: {e}")
