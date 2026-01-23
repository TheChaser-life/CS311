import requests

PRODUCTION_SERVER = 'https://ineedjob.thinhopsops.win/'
STAGING_SERVER = 'xxxx'
BOT_ID = 'xxxx'
USER_ID = 'xxxx'

def request_check():
    try:
        prod_server_request = requests.get(PRODUCTION_SERVER, timeout=10)
        prod_server_status = str(prod_server_request.status_code)
    except:
        prod_server_status = 'TIMEOUT'
    
    try:
        stag_server_request = requests.get(STAGING_SERVER, timeout=10)
        stag_server_status = str(stag_server_request.status_code)
    except: 
        stag_server_status = 'TIMEOUT'
    
    return {
        'prod_status_code':prod_server_status,
        'stag_status_code':stag_server_status
    }

def send_alarms_to_telegram(server_name='PRODUCTION', CODE=404):
    url = f"https://api.telegram.org/bot{BOT_ID}/sendMessage"
    payload = {
        'chat_id':USER_ID,
        'text':f"SERVER {server_name} XẢY RA LỖI, ERROR: {CODE}"
    }
    requests.post(url, json=payload)


if __name__ == '__main__':
    server_status = request_check()
    prod_status_code = server_status['prod_status_code']
    stag_status_code = server_status['stag_status_code']

    if prod_status_code[0] == '5' or prod_status_code == 'TIMEOUT':
        send_alarms_to_telegram('PRODUCTION', prod_status_code)

    if stag_status_code[0] == '5' or stag_status_code == 'TIMEOUT':
        send_alarms_to_telegram('STAGING', stag_status_code)

# Câu lệnh để lập lịch trong file crontab
# * * * * * /usr/bin/python3 /home/user1/python_scripting/server_check.py >> /home/user1/logs/server_check.log 2>&1
