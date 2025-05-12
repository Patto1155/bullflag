import os
import ccxt
import time
import mplfinance as mpf
import numpy as np
import pandas as pd
import openai
from datetime import datetime

# --- CONFIG ---
OPENAI_API_KEY = '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'
openai.api_key = OPENAI_API_KEY
CANDLE_LIMIT = 100
TIMEFRAME = '15m'
CHARTS_DIR = 'charts_live'
RESULTS_FILE = 'live_classification_results.csv'

# Prompts
DETECT_PROMPT = """
You are a trading expert. Does this candlestick chart contain a bull flag pattern? Respond with 'bull_flag' or 'not_bull_flag', and explain your reasoning in 1-2 sentences.
"""
BULL_FLAG_ACTION_PROMPT = """
Based on this bull flag, where would you place a stop loss and take profit? Please provide specific price levels and reasoning.
"""

# Ensure output directory exists
os.makedirs(CHARTS_DIR, exist_ok=True)

def get_binance_markets():
    binance = ccxt.binance()
    tickers = binance.fetch_tickers()
    # Sort by quoteVolume (proxy for liquidity/market cap)
    sorted_markets = sorted(tickers.items(), key=lambda x: x[1].get('quoteVolume', 0), reverse=True)
    # Filter for USDT pairs only
    usdt_pairs = [m for m, t in sorted_markets if m.endswith('/USDT')]
    # Get 50th to 75th
    return usdt_pairs[49:75]

def fetch_ohlcv(pair, limit=CANDLE_LIMIT, timeframe=TIMEFRAME):
    binance = ccxt.binance()
    ohlcv = binance.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('datetime', inplace=True)
    return df[['open','high','low','close']]

def save_chart_image(df, pair):
    fname = f"{pair.replace('/', '_')}_{int(time.time())}.png"
    fpath = os.path.join(CHARTS_DIR, fname)
    mpf.plot(df, type='candle', style='charles', title=pair, ylabel='Price', savefig=fpath)
    return fpath

import base64

def classify_image_with_gpt4o(image_path):
    with open(image_path, 'rb') as img_file:
        img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a trading expert."},
                {"role": "user", "content": [
                    {"type": "text", "text": DETECT_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                ]}
            ],
            max_tokens=256,
        )
    content = response.choices[0].message.content.strip()
    if 'bull_flag' in content.lower():
        pred = 'bull_flag'
    else:
        pred = 'not_bull_flag'
    return pred, content

def bull_flag_action_prompt(image_path):
    with open(image_path, 'rb') as img_file:
        img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a trading expert."},
                {"role": "user", "content": [
                    {"type": "text", "text": BULL_FLAG_ACTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                ]}
            ],
            max_tokens=256,
        )
    return response.choices[0].message.content.strip()

def main():
    pairs = get_binance_markets()
    # Clear results file and write header
    import csv
    with open(RESULTS_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['pair','prediction','reasoning','action','chart_image'])
        writer.writeheader()
    # Write each result after each scan
    for pair in pairs:
        print(f"Scanning {pair}...")
        row = None
        try:
            df = fetch_ohlcv(pair)
            img_path = save_chart_image(df, pair)
            pred, reasoning = classify_image_with_gpt4o(img_path)
            action = ''
            if pred == 'bull_flag':
                action = bull_flag_action_prompt(img_path)
            row = {
                'pair': pair,
                'prediction': pred,
                'reasoning': reasoning,
                'action': action,
                'chart_image': img_path
            }
            print(f"{pair}: {pred} | {action if action else reasoning}")
        except Exception as e:
            err_msg = str(e)
            print(f"Error with {pair}: {err_msg}")
            if 'Invalid interval' in err_msg:
                row = {
                    'pair': pair,
                    'prediction': 'error',
                    'reasoning': 'Binance does not support the 15m interval for this pair.',
                    'action': '',
                    'chart_image': ''
                }
            else:
                row = {
                    'pair': pair,
                    'prediction': 'error',
                    'reasoning': err_msg,
                    'action': '',
                    'chart_image': ''
                }
        # Write the row to the results file
        with open(RESULTS_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['pair','prediction','reasoning','action','chart_image'])
            writer.writerow(row)
    print(f"Results saved to {RESULTS_FILE}")

    # Generate HTML report
    html_path = 'report.html'
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write('<html><head><title>Bull Flag Detection Report</title>')
        f.write('<style>table{border-collapse:collapse;}th,td{border:1px solid #ccc;padding:8px;}img{max-width:300px;}</style></head><body>')
        f.write(f'<h1>Bull Flag Detection Report ({datetime.now().strftime('%Y-%m-%d %H:%M')})</h1>')
        f.write('<table>')
        f.write('<tr><th>Chart</th><th>Pair</th><th>Prediction</th><th>Reasoning</th><th>Action/Advice</th></tr>')
        for row in results:
            img_rel = os.path.relpath(row['chart_image'], '.')
            f.write(f'<tr>')
            f.write(f'<td><a href="{img_rel}"><img src="{img_rel}" alt="chart"></a></td>')
            f.write(f'<td>{row['pair']}</td>')
            f.write(f'<td>{row['prediction']}</td>')
            f.write(f'<td>{row['reasoning'].replace(chr(10), '<br>')}</td>')
            f.write(f'<td>{row['action'].replace(chr(10), '<br>') if row['action'] else ''}</td>')
            f.write(f'</tr>')
        f.write('</table></body></html>')
    print(f"HTML report generated: {html_path}")

if __name__ == '__main__':
    main()
