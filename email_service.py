import requests

def verify_email_with_zerobounce(email):
    api_key = "YOUR_ZEROBOUNCE_API_KEY"
    url = f"https://api.zerobounce.net/v2/validate?api_key={api_key}&email={email}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            result = response.json()
            if result['status'] == "valid":
                return f"Email {email} существует и является действительным."
            elif result['status'] == "invalid":
                return f"Email {email} не существует или недействителен."
            else:
                return f"Email {email} имеет статус: {result['status']}."
        else:
            return f"Ошибка API: {response.status_code}, {response.text}"
    except Exception as e:
        return f"Ошибка при подключении к ZeroBounce: {e}"
