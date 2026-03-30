import requests
import re

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
})

# Try POST form submission like the actual form does
r = session.post('https://html.duckduckgo.com/html/', 
    data={'q': 'site:cricbuzz.com "Fanyan Mughal" cricket profile', 'b': '', 'kl': ''})
print(f"POST Status: {r.status_code}")
print(f"Length: {len(r.text)}")
links = re.findall(r'cricbuzz\.com/profiles/(\d+)/([a-z0-9-]+)', r.text)
print(f"Profile links: {links[:5]}")
if not links:
    # Also try lite.duckduckgo.com
    r2 = session.get('https://lite.duckduckgo.com/lite/', 
        params={'q': 'site:cricbuzz.com "Fanyan Mughal" cricket'})
    print(f"\nLite Status: {r2.status_code}")
    print(f"Lite Length: {len(r2.text)}")
    links2 = re.findall(r'cricbuzz\.com/profiles/(\d+)/([a-z0-9-]+)', r2.text)
    print(f"Lite Profile links: {links2[:5]}")
    if not links2:
        print(r2.text[:500])
