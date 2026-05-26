
import os, re

# Basic emoji and symbol ranges
emoji_pattern = re.compile(
    '['
    '\U0001F600-\U0001F64F'  # emoticons
    '\U0001F300-\U0001F5FF'  # symbols & pictographs
    '\U0001F680-\U0001F6FF'  # transport & map symbols
    '\U0001F1E0-\U0001F1FF'  # flags (iOS)
    '\U00002702-\U000027B0'
    '\U000024C2-\U0001F251'
    ']+', flags=re.UNICODE)

base_dir = r'c:\Users\apurv\OneDrive\Desktop\BREATHESG'

for root, dirs, files in os.walk(base_dir):
    if 'node_modules' in root or '.gemini' in root or '.git' in root:
        continue
    for file in files:
        if file.endswith('.md'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            new_content = emoji_pattern.sub('', content)
            
            if file == 'README.md' and root == base_dir:
                new_content = new_content.replace('analyst / breathesg2024', 'admin@esg.com / admin123')
                new_content = new_content.replace('+-- components/     # Sidebar', '+-- components/     # AppShell, ui')
                
            if new_content != content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f'Updated {path}')
print('Done.')

