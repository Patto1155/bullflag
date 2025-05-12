import os
import threading
import time
from flask import Flask, render_template_string, request, redirect, url_for, send_from_directory
import subprocess

app = Flask(__name__)

# Serve chart images as static files
@app.route('/charts/<path:filename>')
def charts_static(filename):
    charts_dir = os.path.join(app.root_path, 'charts')
    return send_from_directory(charts_dir, filename)

SCAN_SCRIPT = 'scan_markets.py'
REPORT_FILE = 'report.html'
RESULTS_FILE = 'live_classification_results.csv'
scan_thread = None
scan_running = False

TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Bull Flag Scanner Dashboard</title>
    <meta http-equiv="refresh" content="10">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .status { font-weight: bold; color: {{ 'green' if running else 'red' }}; }
        button { padding: 10px 20px; margin: 10px; font-size: 16px; }
        a { font-size: 18px; }
        table { border-collapse: collapse; margin-top: 30px; }
        th, td { border: 1px solid #ccc; padding: 8px; }
        img { max-width: 200px; }
    </style>
    <script>
        setTimeout(function(){ window.location.reload(); }, 10000);
    </script>
</head>
<body>
    <h1>Bull Flag Scanner Dashboard</h1>
    <p>Status: <span class="status">{{ 'RUNNING' if running else 'STOPPED' }}</span></p>
    <form method="post" action="/start">
        <button type="submit" {% if running %}disabled{% endif %}>Start Scanning</button>
    </form>
    <form method="post" action="/stop">
        <button type="submit" {% if not running %}disabled{% endif %}>Stop Scanning</button>
    </form>
    <hr>
    <a href="/{{ report_file }}" target="_blank">View Full HTML Report</a>
    <h2>Latest Scan Results</h2>
    {% if results %}
    <div style="display: flex; flex-wrap: wrap; gap: 32px;">
      {% for row in results %}
        <div style="border: 1px solid #ccc; border-radius: 8px; width: 600px; display: flex; margin-bottom: 24px; background: #fafaff;">
          <div style="flex: 1; padding: 16px; display: flex; align-items: center; justify-content: center; border-right: 1px solid #eee; min-width: 220px;">
            {% if row.chart_image %}
              <a href="{{ row.chart_image }}" target="_blank"><img src="{{ row.chart_image }}" alt="chart" style="max-width:200px; max-height:200px;"></a>
            {% else %}
              <span style="color:#888;">No chart</span>
            {% endif %}
          </div>
          <div style="flex: 2; padding: 16px;">
            <div><b>Pair:</b> {{ row.pair }}</div>
            <div><b>Prediction:</b> {{ row.prediction }}</div>
            <div><b>LLM Response:</b><br>{{ row.reasoning|safe }}</div>
            {% if row.action %}
              <div style="margin-top:8px;"><b>Action/Advice:</b><br>{{ row.action|safe }}</div>
            {% endif %}
          </div>
        </div>
      {% endfor %}
    </div>
    {% else %}
      <p>No scan results yet.</p>
    {% endif %}
</body>
</html>
'''

def scan_loop():
    global scan_running
    while scan_running:
        subprocess.run(['python', SCAN_SCRIPT])
        # Wait 10 minutes before next scan
        for _ in range(60):
            if not scan_running:
                break
            time.sleep(10)

def start_scanning():
    global scan_thread, scan_running
    if not scan_running:
        scan_running = True
        scan_thread = threading.Thread(target=scan_loop, daemon=True)
        scan_thread.start()

def stop_scanning():
    global scan_running
    scan_running = False

def load_latest_results():
    import csv
    results = []
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Always use just the filename, never a path
                if row['chart_image']:
                    img_filename = os.path.basename(row['chart_image'])
                    img_path = '/charts/' + img_filename
                else:
                    img_path = ''
                results.append({
                    'chart_image': img_path,
                    'pair': row['pair'],
                    'prediction': row['prediction'],
                    'reasoning': row['reasoning'].replace('\n', '<br>') if row['reasoning'] else '',
                    'action': row['action'].replace('\n', '<br>') if row['action'] else ''
                })
    return results

@app.route('/')
def index():
    results = load_latest_results()
    return render_template_string(TEMPLATE, running=scan_running, report_file=REPORT_FILE, results=results)

@app.route('/start', methods=['POST'])
def start():
    start_scanning()
    return redirect(url_for('index'))

@app.route('/stop', methods=['POST'])
def stop():
    stop_scanning()
    return redirect(url_for('index'))

@app.route(f'/{REPORT_FILE}')
def serve_report():
    return app.send_static_file(REPORT_FILE)

if __name__ == '__main__':
    # Ensure the report file is in the static folder for serving
    static_folder = os.path.join(app.root_path, 'static')
    os.makedirs(static_folder, exist_ok=True)
    if os.path.exists(REPORT_FILE):
        os.replace(REPORT_FILE, os.path.join(static_folder, REPORT_FILE))
    app.static_folder = static_folder
    app.run(debug=True, port=5000)
