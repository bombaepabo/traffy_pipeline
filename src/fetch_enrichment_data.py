import requests
import pandas as pd
import holidays
import os
from datetime import datetime

def build_date_dimension():
    print("🌤️ Fetching historical weather data for Bangkok...")
    
    # 1. Fetch Weather Data from Open-Meteo
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": 13.75,
        "longitude": 100.50,
        "start_date": "2022-01-01",
        "end_date": datetime.today().strftime('%Y-%m-%d'),
        "daily": ["precipitation_sum", "temperature_2m_max"],
        "timezone": "Asia/Bangkok"
    }
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    weather_data = response.json()
    
    # Create pandas DataFrame
    df = pd.DataFrame({
        'date': weather_data['daily']['time'],
        'precipitation_mm': weather_data['daily']['precipitation_sum'],
        'max_temp_c': weather_data['daily']['temperature_2m_max']
    })
    
    # Convert date column to actual datetime objects
    df['date'] = pd.to_datetime(df['date'])
    
    # 2. Add Calendar Features (Is it a weekend?)
    print("📅 Calculating weekends and calendar features...")
    # dt.dayofweek returns 5 for Saturday and 6 for Sunday
    df['is_weekend'] = df['date'].dt.dayofweek.isin([5, 6])
    
    # 3. Add Thai Public Holidays
    print("🐘 Generating official Thai Public Holidays...")
    # Get holidays for 2024 (and 2025 just in case we are in the new year)
    th_holidays = holidays.TH(years=[2022, 2023, 2024, 2025])
    
    # Check if each date is in the holiday dictionary
    df['is_holiday'] = df['date'].apply(lambda d: d in th_holidays)
    # Get the actual name of the holiday (e.g. "Songkran Festival")
    df['holiday_name'] = df['date'].apply(lambda d: th_holidays.get(d) if d in th_holidays else None)
    
    # Clean up empty temperatures/rainfall with 0
    df = df.fillna({'precipitation_mm': 0.0, 'max_temp_c': 30.0})
    
    # 4. Save directly into our dbt seeds folder!
    # Ensure the path is correct relative to where the script is executed
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_path = os.path.join(project_root, 'bangkok_urban_dbt', 'seeds', 'dim_date_enriched.csv')
    
    df.to_csv(output_path, index=False)
    print(f"✅ Success! Master Date Dimension saved to: {output_path}")
    print(f"📊 Total Rows Generated: {len(df)}")

if __name__ == "__main__":
    build_date_dimension()
