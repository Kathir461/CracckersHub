import urllib.request

urls = [
    'http://127.0.0.1:5000/',
    'http://127.0.0.1:5000/static/manifest-customer.json',
    'http://127.0.0.1:5000/service-worker.js',
]
for url in urls:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            print(url, r.status, r.getheader('Content-Type'))
            print(r.read(200).decode('utf-8', 'replace'))
    except Exception as e:
        print(url, 'ERROR', e)
