import sqlite3
from datetime import datetime

# Connect to database
conn = sqlite3.connect('signage.db')

# Insert test devices
test_devices = [
    ('SPOOF001', 'SPOOF-DEVICE-001', '192.168.1.201'),
    ('SPOOF002', 'SPOOF-DEVICE-002', '192.168.1.202')
]

for device_id, device_name, ip_address in test_devices:
    conn.execute('''
        INSERT OR IGNORE INTO devices 
        (device_id, device_name, custom_name, location, last_checkin, is_active, ip_address, app_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (device_id, device_name, None, None, datetime.now(), 1, ip_address, '1.0'))

conn.commit()

# Verify insertion
cursor = conn.execute("SELECT device_id, device_name, ip_address FROM devices WHERE device_id LIKE 'SPOOF%'")
results = cursor.fetchall()

print("Test devices added:")
for row in results:
    print(f"  {row[0]} | {row[1]} | {row[2]}")

conn.close()
print("Done!")