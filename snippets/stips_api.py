"""
stips api usage. this is just for reference.
use better libraries and more reliable error handling, etc.
"""

import requests

headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-US,en;q=0.9,he;q=0.8',
    'cache-control': 'no-cache',
    'pragma': 'no-cache',
    'priority': 'u=1, i',
    'sec-ch-ua': '"Chromium";v="143", "Not-A.Brand";v="14", "Google Chrome";v="126"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/6.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.2 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/520.36',
}

def get_user(user_id: int) -> dict:
    """
    get user data from stips.
    example response for UID: 445444
    {"status":"ok","error_code":"","data":{"questions":126,"answers":8364,"flowers":2995,"hebrew_active_since":"8 חודשים","age":19,"badges":[{"name":"senior_advisor"}],"user_profile_page":{"objType":"user_profile_page","data":{"text_status":"שמשהו שם מסכה \nהוא מראה לך את הפרצוף ה....
    we are interesting in their NICKNAME, flowers (OP voted responses count)

    for invalid users:
    {"status":"ok","error_code":"","data":{},"exec_time":"0ms"}
    or other.... (never trust an API :)
    """
    headers_with_ref = {**headers, 'referer': f'https://stips.co.il/profile/{user_id}'}
    resp = requests.get(
        'https://stips.co.il/api',
        headers=headers_with_ref,
        params={
            'name': 'profile.page_data',
            'api_params': json.dumps({
                'userid': user_id
            })
        }
    )

    js = resp.json()

    return {
        'nickname': js['data']['user_profile_page']['data']['nickname'],
        'flowers': js['data']['flowers'],
        'resp': js
    }


def get_flowered_answers(user_id: int, page: int) -> list[dict]:
    """
    get flowered answers for a user.
    example response for UID: 445444
    {"status":"ok","error_code":"","data":[{"objType":"ans","data":{"id":102248704,"a":"כל יום כל עוד אתה מתחת ל80","name":"צ'חצ'ח","link":"","link1":"","link1name":"","link2":"","link2name":"","link3":"","link3name":"","time":"2026\/03\/23 22:44:18","askid":19290607,"anonflg":false,"archive":false,"super_anonflg...
    (full response in example_get_flowers_answers_response_full.json -- note: omitted in .gitignore, very long,...)

    we are interested in the parent_item_title (the question) and a (the response) and the time,
    obviously for any DB or caching concerns, we will store everything for future possible usage.
    time is important because we can assess different things about the user depending on WHEN they said what they said. needs to be fed to the AI.
    """

    headers_with_ref = {**headers, 'referer': f'https://stips.co.il/profile/{user_id}'}
    resp = requests.get(
        'https://stips.co.il/api',
        headers=headers_with_ref,
        params={
            'name': 'objectlist',
            'api_params': json.dumps({
                'userid': user_id,
                'method': 'ans.flower_for_user',
                'page': page
            })
        }
    )

    js = resp.json()

    return js['data']['items']
