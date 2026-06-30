import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from google.cloud import bigquery
from google.cloud import pubsub_v1
import os
import json
import urllib.request
import pydeck as pdk

# --- 1. SETUP & CONFIGURATION ---
st.set_page_config(page_title="การกำกับดูแลเมืองกรุงเทพมหานคร", page_icon="🏙️", layout="wide")
# We no longer hardcode credentials.json. We will use Google Cloud Run's built-in Service Account (Keyless Auth)
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "credentials.json"

st.title("🏙️ แดชบอร์ดการจัดการปัญหาเมืองกรุงเทพมหานคร")

# --- 2. DATA LOADING (BIGQUERY) ---
@st.cache_data(ttl=600)
def load_historical_data():
    client = bigquery.Client()
    
    # We use a LEFT JOIN so that even districts with 0 complaints appear on the map!
    query = """
        SELECT 
            d.district_th, 
            COALESCE(count(f.ticket_id), 0) as total_complaints
        FROM `scrimterz-bangkok-urban.warehouse_gold.dim_districts` d
        LEFT JOIN `scrimterz-bangkok-urban.warehouse_gold.mask_fact_complaints` f
          ON d.district_th = f.district_th
        GROUP BY d.district_th
    """
    return client.query(query).to_dataframe()

@st.cache_data(ttl=3600)
def load_geojson():
    """Cache the GeoJSON so we don't re-download from GitHub on every rerun."""
    with urllib.request.urlopen("https://raw.githubusercontent.com/pcrete/gsvloader-demo/master/geojson/Bangkok-districts.geojson") as url:
        return json.load(url)

with st.spinner("กำลังดึงข้อมูลจากคลังข้อมูล..."):
    df = load_historical_data()

# Calculate some quick stats for the KPIs
total_tickets = df['total_complaints'].sum()
top_district = df.sort_values(by='total_complaints', ascending=False).iloc[0]

# --- 3. UI LAYOUT: KPIs ---
st.markdown("---")
m1, m2, m3 = st.columns(3)
m1.metric("จำนวนเรื่องร้องเรียนทั้งหมด", f"{total_tickets:,}")
m2.metric("เขตที่มีเรื่องร้องเรียนสูงสุด", top_district['district_th'])
m3.metric("สถานะระบบ", "🟢 กำลังสตรีมแบบเรียลไทม์")
st.markdown("---")


# =====================================================================
# SECTION 1: GEOGRAPHICAL INCIDENT MAPPING
# =====================================================================
st.header("📍 1. แผนที่แสดงจุดเกิดเหตุทางภูมิศาสตร์")
st.markdown("ระบุเขตที่มีปริมาณเรื่องร้องเรียนสูงสุดทั่วกรุงเทพฯ ด้วยการวิเคราะห์เชิงพื้นที่แบบโต้ตอบ")

col1, col2 = st.columns([1, 3])

with col1:
    st.subheader("เขตตามปริมาณเรื่องร้องเรียน")
    st.dataframe(
        df.sort_values(by='total_complaints', ascending=False),
        column_config={
            "district_th": "ชื่อเขต",
            "total_complaints": st.column_config.ProgressColumn(
                "ปริมาณเรื่องร้องเรียน",
                help="จำนวนเรื่องร้องเรียนทั้งหมด",
                format="%d",
                min_value=0,
                max_value=int(df['total_complaints'].max()),
            )
        },
        hide_index=True,
        height=800, 
        use_container_width=True
    )
    
with col2:
    st.subheader("แผนที่อินเทอร์แอคทีฟ (Choropleth Map)")
    with st.spinner("กำลังสร้างแผนที่..."):
        bangkok_geojson = load_geojson()
        
        df_map = df.copy()
        df_map['Percentage'] = (df_map['total_complaints'] / total_tickets) * 100
        df_map['Percentage'] = df_map['Percentage'].map('{:.1f}%'.format)
        
        centroids = []
        for feature in bangkok_geojson['features']:
            name = feature['properties']['dname']
            geom = feature['geometry']
            lons, lats = [], []
            
            if geom['type'] == 'Polygon':
                coords = geom['coordinates'][0]
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
            elif geom['type'] == 'MultiPolygon':
                for poly in geom['coordinates']:
                    coords = poly[0]
                    lons.extend([c[0] for c in coords])
                    lats.extend([c[1] for c in coords])
                    
            if lons and lats:
                center_lat = (min(lats) + max(lats)) / 2
                center_lon = (min(lons) + max(lons)) / 2
                centroids.append({'district_th': name, 'lat': center_lat, 'lon': center_lon})
        
        df_centroids = pd.DataFrame(centroids)
        df_map = df_map.merge(df_centroids, on='district_th', how='left')
        
        fig_map = px.choropleth(
            df_map, 
            geojson=bangkok_geojson, 
            locations='district_th', 
            featureidkey="properties.dname",
            color='total_complaints',
            color_continuous_scale="Oranges", 
            
            hover_name='district_th', 
            hover_data={
                'district_th': False, 
                'lat': False,
                'lon': False,
                'total_complaints': True, 
                'Percentage': True        
            },
            labels={'total_complaints': 'เรื่องร้องเรียน'}
        )
        
        top_5_df = df_map.sort_values(by='total_complaints', ascending=False).head(5)
        
        fig_map.add_scattergeo(
            lon=top_5_df['lon'],
            lat=top_5_df['lat'],
            text=top_5_df['Percentage'],
            mode='text',
            textfont=dict(color='white', size=13, family='sans-serif'),
            hoverinfo='skip' 
        )
        
        fig_map.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
        fig_map.update_traces(marker_line_width=0.5, marker_line_color="#444444")
        
        fig_map.update_layout(
            height=800,
            margin={"r":0,"t":0,"l":0,"b":0},
            geo=dict(bgcolor='rgba(0,0,0,0)'),
            paper_bgcolor='rgba(0,0,0,0)'
        )
        
    st.plotly_chart(fig_map, use_container_width=True)

st.markdown("---")

# =====================================================================
# SECTION 1.5: TICKET-LEVEL SCATTER MAP
# =====================================================================
st.header("🔍 แผนที่ระดับ Ticket (ซูมเพื่อดูรายละเอียด)")
st.caption("💡 **เคล็ดลับ:** เลือกประเภทปัญหาเพื่อดูตำแหน่ง · ซูมเข้า-ออกเพื่อสำรวจรายละเอียด · คลิกที่จุดเพื่อดูข้อมูล")

@st.cache_data(ttl=600)
def load_ticket_points():
    client = bigquery.Client()
    query = """
        SELECT
            ticket_id,
            district_th,
            approx_latitude,
            approx_longitude,
            status,
            has_flooding_issue,
            has_pothole_issue,
            has_dark_street_issue,
            has_garbage_issue
        FROM `scrimterz-bangkok-urban.warehouse_gold.mask_fact_complaints`
        WHERE approx_latitude IS NOT NULL 
          AND approx_longitude IS NOT NULL
          AND approx_latitude BETWEEN 13.4 AND 14.0
          AND approx_longitude BETWEEN 100.3 AND 100.9
    """
    return client.query(query).to_dataframe()

with st.spinner("กำลังโหลดตำแหน่งเรื่องร้องเรียนทั้งหมด..."):
    df_points = load_ticket_points()

# Category filter using horizontal radio buttons
scatter_category = st.radio(
    "เลือกประเภทปัญหา:",
    options=["ทั้งหมด", "น้ำท่วม", "ถนน", "แสงสว่าง", "ความสะอาด"],
    horizontal=True,
    key="scatter_category_radio"
)

# Filter based on selection
flag_map = {
    'น้ำท่วม': 'has_flooding_issue',
    'ถนน': 'has_pothole_issue',
    'แสงสว่าง': 'has_dark_street_issue',
    'ความสะอาด': 'has_garbage_issue',
}

if scatter_category == "ทั้งหมด":
    df_map_filtered = df_points.copy()
else:
    col = flag_map[scatter_category]
    df_map_filtered = df_points[df_points[col] == True].copy()

# Assign a display category for coloring
def get_category(row):
    if row['has_flooding_issue']: return 'น้ำท่วม'
    if row['has_pothole_issue']: return 'ถนน'
    if row['has_dark_street_issue']: return 'แสงสว่าง'
    if row['has_garbage_issue']: return 'ความสะอาด'
    return 'อื่นๆ'

df_map_filtered['ประเภท'] = df_map_filtered.apply(get_category, axis=1)

st.markdown(f"**แสดงผล {len(df_map_filtered):,} จุด** สำหรับประเภท: `{scatter_category}`")

scatter_colors = {
    'น้ำท่วม': '#1565C0',    # Dark Blue
    'ถนน': '#D84315',        # Deep Orange/Red
    'แสงสว่าง': '#6A1B9A',      # Deep Purple
    'ความสะอาด': '#2E7D32',    # Dark Green
    'อื่นๆ': '#424242',        # Dark Grey
}

fig_scatter_map = px.scatter_mapbox(
    df_map_filtered,
    lat="approx_latitude",
    lon="approx_longitude",
    color="ประเภท",
    color_discrete_map=scatter_colors,
    hover_data={
        'ticket_id': True,
        'district_th': True,
        'status': True,
        'approx_latitude': False,
        'approx_longitude': False,
    },
    labels={
        'ticket_id': 'รหัส Ticket',
        'district_th': 'เขต',
        'status': 'สถานะ',
        'ประเภท': 'ประเภทปัญหา'
    },
    zoom=10,
    center={"lat": 13.75, "lon": 100.52},
    mapbox_style="open-street-map"
)

fig_scatter_map.update_traces(
    marker=dict(size=12, opacity=1.0)
)
fig_scatter_map.update_layout(
    height=700,
    margin={"r":0,"t":0,"l":0,"b":0},
    legend=dict(
        orientation="h",
        yanchor="top", y=0.99,
        xanchor="center", x=0.5,
        bgcolor="rgba(0,0,0,0.6)",
        font=dict(color="white", size=14)
    )
)
st.plotly_chart(fig_scatter_map, use_container_width=True)

st.markdown("---")



st.header("📈 2. การวิเคราะห์เชิงทำนาย (สภาพอากาศและปฏิทิน)")
st.markdown("เราได้รวมข้อมูลเรื่องร้องเรียนภายในกับข้อมูลภายนอก **Open-Meteo Weather API** และ **ปฏิทินวันหยุดไทย** เพื่อค้นหาความสัมพันธ์เชิงสาเหตุเชิงลึก!")
st.caption("💡 **เคล็ดลับ:** คลิกที่ชื่อหมวดหมู่ใน Legend เพื่อเปิด/ปิดแต่ละประเภท · ดับเบิลคลิกเพื่อแสดงเฉพาะประเภทนั้น")

@st.cache_data(ttl=600)
def load_enriched_data():
    client = bigquery.Client()
    query = """
        SELECT * FROM `scrimterz-bangkok-urban.warehouse_gold.fact_complaints_enriched`
        ORDER BY date
    """
    return client.query(query).to_dataframe()

with st.spinner("กำลังดึงข้อมูลพหุมิติที่ผ่านการเพิ่มพูน (Enriched)..."):
    df_enriched = load_enriched_data()
    df_enriched['date'] = pd.to_datetime(df_enriched['date'])

# Define a professional color palette for categories
category_colors = {
    'น้ำท่วม': '#2196F3',       # Blue
    'ถนน': '#FF9800',           # Orange  
    'แสงสว่าง': '#FFC107',      # Amber
    'ความสะอาด': '#4CAF50',     # Green
    'อื่นๆ': '#9E9E9E',         # Grey
}

types = sorted(list(df_enriched['complaint_type'].dropna().unique()))

# --- CHART 1: Multi-line Rainfall vs ALL Categories ---
st.markdown("#### ปริมาณน้ำฝนส่งผลให้เกิดการร้องเรียนประเภทใดมากที่สุด?")

fig_timeline = make_subplots(specs=[[{"secondary_y": True}]])

# Rainfall as a soft blue area (background layer)
# Use the first category's date/rainfall since rainfall is the same for all categories on a given date
df_rain = df_enriched.drop_duplicates(subset=['date']).sort_values('date')
fig_timeline.add_trace(
    go.Scatter(
        x=df_rain['date'], y=df_rain['precipitation_mm'],
        name="ปริมาณน้ำฝน (มม.)",
        fill='tozeroy',
        line=dict(color='rgba(0, 150, 255, 0.3)'),
        mode='lines',
        fillcolor='rgba(0, 150, 255, 0.15)'
    ),
    secondary_y=False
)

# Add a line for EACH complaint category
for cat in types:
    df_cat = df_enriched[df_enriched['complaint_type'] == cat].sort_values('date')
    color = category_colors.get(cat, '#888888')
    fig_timeline.add_trace(
        go.Scatter(
            x=df_cat['date'], y=df_cat['total_complaints'],
            name=cat,
            mode='lines+markers',
            line=dict(color=color, width=2.5, shape='spline'),
            marker=dict(size=6)
        ),
        secondary_y=True
    )

fig_timeline.update_yaxes(title_text="ปริมาณน้ำฝน (มม.)", secondary_y=False)
fig_timeline.update_yaxes(title_text="จำนวนเรื่องร้องเรียน", secondary_y=True)
fig_timeline.update_layout(
    height=500, 
    margin=dict(t=30, b=0, l=0, r=0), 
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
)
st.plotly_chart(fig_timeline, use_container_width=True)

# --- CHARTS 2 & 3: Side by Side ---
c1, c2 = st.columns(2)

with c1:
    st.markdown("#### อุณหภูมิ vs เรื่องร้องเรียน (แยกตามประเภท)")
    fig_scatter = px.scatter(
        df_enriched, x="max_temp_c", y="total_complaints",
        color="complaint_type",
        color_discrete_map=category_colors,
        labels={
            "max_temp_c": "อุณหภูมิสูงสุดรายวัน (°C)", 
            "total_complaints": "จำนวนเรื่องร้องเรียน",
            "complaint_type": "ประเภท"
        },
        opacity=0.7
    )
    fig_scatter.update_traces(marker=dict(size=8))
    fig_scatter.update_layout(
        height=450, 
        margin=dict(t=30, b=0, l=0, r=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

with c2:
    st.markdown("#### วันธรรมดา vs วันหยุด (แยกตามประเภท)")
    df_cal = df_enriched.groupby(['complaint_type', 'is_weekend'])['total_complaints'].mean().reset_index()
    df_cal['ประเภทวัน'] = df_cal['is_weekend'].map({True: 'วันหยุด (เสาร์/อาทิตย์)', False: 'วันธรรมดา (จันทร์-ศุกร์)'})
    
    fig_grouped = px.bar(
        df_cal, x="complaint_type", y="total_complaints", 
        color="ประเภทวัน", barmode="group",
        text_auto='.1f',
        color_discrete_map={'วันหยุด (เสาร์/อาทิตย์)': '#333333', 'วันธรรมดา (จันทร์-ศุกร์)': '#F95335'},
        labels={
            "complaint_type": "ประเภทเรื่องร้องเรียน", 
            "total_complaints": "จำนวนเฉลี่ยต่อวัน"
        }
    )
    fig_grouped.update_layout(
        height=450, 
        margin=dict(t=30, b=0, l=0, r=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig_grouped, use_container_width=True)


st.markdown("---")

# =====================================================================
# SECTION 3: LIVE EVENT STREAMING
# =====================================================================
st.header("🔴 3. สตรีมข้อมูลเหตุการณ์สด (Pub/Sub Streaming)")
st.markdown("ติดตามเรื่องร้องเรียนจากประชาชนแบบเรียลไทม์โดยตรงจากสตรีม Kafka/PubSub")

if st.button("ดึงข้อมูลเรื่องร้องเรียนล่าสุด"):
    with st.spinner("กำลังรอรับข้อมูลจาก Google Pub/Sub..."):
        subscriber = pubsub_v1.SubscriberClient()
        subscription_path = subscriber.subscription_path('scrimterz-bangkok-urban', 'bangkok-urban-events-sub')
        
        response = subscriber.pull(request={"subscription": subscription_path, "max_messages": 5})
        
        if not response.received_messages:
            st.info("ขณะนี้ยังไม่มีเรื่องร้องเรียนใหม่ ลองอีกครั้งในไม่กี่วินาที!")
        else:
            ack_ids = []
            for msg in response.received_messages:
                ticket = json.loads(msg.message.data.decode('utf-8'))
                
                issue_type = ticket.get('type') or 'ปัญหาที่ไม่ทราบประเภท'
                address = ticket.get('address') or 'กรุงเทพมหานคร'
                
                st.warning(f"🚨 **เรื่องร้องเรียนใหม่:** รายงานปัญหา {issue_type} ที่ {address}!")
                ack_ids.append(msg.ack_id)
            
            subscriber.acknowledge(request={"subscription": subscription_path, "ack_ids": ack_ids})

# (End of file)
