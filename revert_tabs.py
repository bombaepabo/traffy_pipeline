import os

file_path = 'streamlit/app.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.read().split('\n')

new_lines = lines[:50]
new_lines.append('# --- 4. UI LAYOUT: TABS ---')
new_lines.append('tab1, tab2, tab3 = st.tabs(["🏛️ Historical Analytics (Batch)", "🔴 Live Event Stream (Pub/Sub)", "📈 Advanced Analytics (Enriched)"])')
new_lines.append('')
new_lines.append('# TAB 1: Analytics')
new_lines.append('with tab1:')
for line in lines[51:159]:
    new_lines.append('    ' + line if line else '')
    
new_lines.append('')
new_lines.append('# TAB 2: Live Stream')
new_lines.append('with tab2:')
for line in lines[242:269]:
    new_lines.append('    ' + line if line else '')
    
new_lines.append('')
new_lines.append('# TAB 3: Advanced Analytics')
new_lines.append('with tab3:')
for line in lines[162:240]:
    new_lines.append('    ' + line if line else '')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines) + '\n')
