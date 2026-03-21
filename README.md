# Weather Dashboard

A complete Python-based application that automatically fetches, stores, and visualizes historical weather data (daily min/max temperatures) for any given city (defaults to Porto, Portugal).

## Project Architecture
1. **Weather Fetcher (`fetch_weather.py`)**: A script that pulls daily min/max temperatures from the Open-Meteo archive API and stores them securely in a PostgreSQL Database using an Upsert mechanism. It's meant to be run daily.
2. **Dashboard (`dashboard.py`)**: A Flask web application that serves an elegant, responsive interface using Chart.js to report exactly what you have stored in your database.

---

## 🚀 Deployment Guide (AWS EC2 + RDS)

This guide is designed for users with basic AWS and Python knowledge.

### Step 1: Set up the Database (AWS RDS)
1. In your AWS Console, navigate to **RDS** and click **Create database**.
2. Select **PostgreSQL**. The "Free tier" template is completely fine.
3. In settings, set the **DB instance identifier**, **Master username** (default: `postgres`), and create a **Master password** (save this!).
4. Ensure the database is placed in a Security Group that will allow traffic (Port 5432) from your EC2 instance.
5. Once created, copy the **Endpoint** URL—this is your `DB_HOST`.

### Step 2: Set up the Server (AWS EC2)
1. Go to **EC2** and click **Launch instance**.
2. Select an **Ubuntu** AMI (Free tier eligible).
3. In Security Groups, allow **SSH (22)** to connect to it, and allow **TCP Port 5000** if you want to access the Flask app publicly over the internet without a reverse proxy.
4. Launch the instance and connect to it.

### Step 3: Clone and Prepare
SSH into your EC2 instance and run the following commands to install dependencies:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv libpq-dev git -y

git clone https://github.com/saeedm31/Porto_weather.git
cd Porto_weather

# Set up a virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### Step 4: Configuration
Create your environment variables file securely on the server:

```bash
cp .env.example .env
nano .env
```

Fill in the RDS details you noted earlier:
```env
DB_HOST=your-rds-endpoint.amazonaws.com
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASS=your_super_secret_password

# You can also change the target city coordinates here! Default is Porto.
CITY_LAT=41.15
CITY_LON=-8.61
```
Press `Ctrl+O`, `Enter`, and `Ctrl+X` to save and exit nano.

### Step 5: Initialize the Database
Run the setup script to create the required `porto_weather` table:
```bash
python3 setup_db.py
```
*If everything is correct, it will say "✅ Table porto_weather is ready."*

### Step 6: First Run
Run the fetcher manually the first time to backfill your historical data (from Jan 1, 2023 up to today):
```bash
python3 fetch_weather.py
```

Then, start the dashboard!
```bash
./run_dashboard.sh
```
You can now open `http://<YOUR_EC2_PUBLIC_IP>:5000` to see your animated weather dashboard!

### Step 7: Automation (Cron Job)
To make your server update the database automatically every morning, add a cron job:

```bash
crontab -e
```
Add this line to automatically fetch yesterday's weather every day at 6:00 AM:
```text
0 6 * * * /home/ubuntu/Porto_weather/cron_update.sh
```
