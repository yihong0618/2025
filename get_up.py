import argparse

import pendulum
import requests
import telebot
from github import Github

# 1 real get up #5 for test
GET_UP_ISSUE_NUMBER = 1
GET_UP_MESSAGE_TEMPLATE = "今天的起床时间是--{get_up_time}.\r\n\r\n起床啦。\r\n\r\n今天的一句诗:\r\n{sentence}\r\n"
# in 2024-06-15 this one ssl error
SENTENCE_API = "https://v1.jinrishici.com/all"

DEFAULT_SENTENCE = (
    "赏花归去马如飞\r\n去马如飞酒力微\r\n酒力微醒时已暮\r\n醒时已暮赏花归\r\n"
)
TIMEZONE = "Asia/Shanghai"


def login(token):
    return Github(token)


def get_one_sentence():
    try:
        r = requests.get(SENTENCE_API)
        if r.ok:
            return r.json()["content"]
        return DEFAULT_SENTENCE
    except Exception:
        print("get SENTENCE_API wrong")
        return DEFAULT_SENTENCE


def get_today_get_up_status(issue):
    comments = list(issue.get_comments())
    if not comments:
        return False, []
    latest_comment = comments[-1]
    now = pendulum.now(TIMEZONE)
    latest_day = pendulum.instance(latest_comment.created_at).in_timezone(
        "Asia/Shanghai"
    )
    is_today = (latest_day.day == now.day) and (latest_day.month == now.month)
    return is_today


def make_get_up_message():
    sentence = get_one_sentence()
    now = pendulum.now(TIMEZONE)
    # 3 - 7 means early for me
    ###  make it to 9 in 2024.10.15 for maybe I forgot it ###
    is_get_up_early = 3 <= now.hour <= 9
    try:
        sentence = get_one_sentence()
        print(f"Second: {sentence}")
    except Exception as e:
        print(str(e))
    return sentence, is_get_up_early


def main(
    github_token,
    repo_name,
    weather_message,
    tele_token,
    tele_chat_id,
):
    u = login(github_token)
    repo = u.get_repo(repo_name)
    issue = repo.get_issue(GET_UP_ISSUE_NUMBER)
    is_today = get_today_get_up_status(issue)
    if is_today:
        print("Today I have recorded the wake up time")
        return
    sentence, is_get_up_early = make_get_up_message()
    get_up_time = pendulum.now(TIMEZONE).to_datetime_string()
    body = GET_UP_MESSAGE_TEMPLATE.format(get_up_time=get_up_time, sentence=sentence)

    if is_get_up_early:
        issue.create_comment(body)
        # send to telegram
        if tele_token and tele_chat_id:
            bot = telebot.TeleBot(tele_token)
            try:
                # sleep for waiting for the image to be generated
                bot.send_message(tele_chat_id, body, disable_notification=True)
            except Exception as e:
                print(str(e))
    else:
        print("You wake up late, test")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("github_token", help="github_token")
    parser.add_argument("repo_name", help="repo_name")
    parser.add_argument(
        "--weather_message", help="weather_message", nargs="?", default="", const=""
    )
    parser.add_argument(
        "--tele_token", help="tele_token", nargs="?", default="", const=""
    )
    parser.add_argument(
        "--tele_chat_id", help="tele_chat_id", nargs="?", default="", const=""
    )
    options = parser.parse_args()
    main(
        options.github_token,
        options.repo_name,
        options.weather_message,
        options.tele_token,
        options.tele_chat_id,
    )
