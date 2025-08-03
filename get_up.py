import argparse
import tempfile

import duckdb
import pendulum
import requests
import telebot
from github import Github
from telegramify_markdown import markdownify

# 1 real get up #5 for test
GET_UP_ISSUE_NUMBER = 1
GET_UP_MESSAGE_TEMPLATE = """今天的起床时间是--{get_up_time}。

起床啦。

今天是今年的第 {day_of_year} 天。

{github_activity}

{running_info}

今天的一句诗:
{sentence}
"""
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


def get_yesterday_github_activity(github_token=None, username="yihong0618"):
    """获取昨天的 GitHub PR、Issues 和 Star 活动（北京时间）"""
    try:
        # 使用北京时间计算昨天
        yesterday = pendulum.now(TIMEZONE).subtract(days=1)
        yesterday_start = yesterday.start_of("day").in_timezone("UTC")
        yesterday_end = yesterday.end_of("day").in_timezone("UTC")

        activities = []

        # 使用公开 API 获取用户活动
        url = f"https://api.github.com/users/{username}/events"
        headers = {}
        if github_token:
            headers["Authorization"] = f"token {github_token}"

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            events = response.json()

            for event in events[:100]:  # 检查最近100个事件，增加数量以确保捕获所有活动
                event_created = pendulum.parse(event["created_at"])

                # 检查是否在昨天的时间范围内
                if yesterday_start <= event_created <= yesterday_end:
                    event_type = event["type"]
                    repo_name = event["repo"]["name"]

                    if event_type == "PullRequestEvent":
                        action = event["payload"].get("action")
                        if action == "opened":
                            pr_data = event["payload"]["pull_request"]
                            pr_title = pr_data["title"]
                            pr_url = pr_data["html_url"]
                            activities.append(
                                f"创建了 PR: [{pr_title}]({pr_url}) ({repo_name})"
                            )
                        elif action == "merged":
                            pr_data = event["payload"]["pull_request"]
                            pr_title = pr_data["title"]
                            pr_url = pr_data["html_url"]
                            activities.append(
                                f"合并了 PR: [{pr_title}]({pr_url}) ({repo_name})"
                            )
                    elif event_type == "IssuesEvent":
                        action = event["payload"].get("action")
                        if action == "opened":
                            issue_data = event["payload"]["issue"]
                            issue_title = issue_data["title"]
                            issue_url = issue_data["html_url"]
                            activities.append(
                                f"创建了 Issue: [{issue_title}]({issue_url}) ({repo_name})"
                            )
                        elif action == "closed":
                            issue_data = event["payload"]["issue"]
                            issue_title = issue_data["title"]
                            issue_url = issue_data["html_url"]
                            activities.append(
                                f"关闭了 Issue: [{issue_title}]({issue_url}) ({repo_name})"
                            )
                    elif event_type == "WatchEvent":  # Star 事件
                        action = event["payload"].get("action")
                        if action == "started":  # started 表示 star 了仓库
                            repo_name = event["repo"]["name"]
                            repo_url = f"https://github.com/{repo_name}"
                            activities.append(f"Star 了项目: [{repo_name}]({repo_url})")
                elif event_created < yesterday_start:
                    # 超出时间范围，停止搜索
                    break
        else:
            print(f"GitHub API 请求失败: {response.status_code}")
            return ""

        if activities:
            # 去重并限制数量
            unique_activities = list(dict.fromkeys(activities))
            return "昨天的 GitHub 活动：\n" + "\n".join(
                f"• {activity}" for activity in unique_activities[:8]  # 增加显示数量
            )
        else:
            return ""

    except Exception as e:
        print(f"Error getting GitHub activity: {e}")
        return ""


def get_running_distance():
    """获取跑步距离信息（昨天、本月、今年的统计）"""
    try:
        # 下载 parquet 文件
        url = "https://github.com/yihong0618/run/raw/refs/heads/master/run_page/data.parquet"
        response = requests.get(url)

        if not response.ok:
            return ""

        # 使用 duckdb 读取 parquet 数据
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_file.write(response.content)
            temp_file.flush()

            conn = duckdb.connect()

            # 获取北京时间的日期
            now = pendulum.now(TIMEZONE)
            yesterday = now.subtract(days=1)
            month_start = now.start_of("month")
            year_start = now.start_of("year")

            # 昨天的跑步统计（距离单位是米，转换为公里）
            yesterday_query = f"""
            SELECT 
                COUNT(*) as count,
                ROUND(SUM(distance)/1000, 2) as total_km
            FROM read_parquet('{temp_file.name}')
            WHERE DATE(start_date_local) = '{yesterday.to_date_string()}'
            """

            # 本月的跑步统计
            month_query = f"""
            SELECT 
                COUNT(*) as count,
                ROUND(SUM(distance)/1000, 2) as total_km
            FROM read_parquet('{temp_file.name}')
            WHERE start_date_local >= '{month_start.to_date_string()}' 
                AND start_date_local < '{now.add(days=1).to_date_string()}'
            """

            # 今年的跑步统计
            year_query = f"""
            SELECT 
                COUNT(*) as count,
                ROUND(SUM(distance)/1000, 2) as total_km
            FROM read_parquet('{temp_file.name}')
            WHERE start_date_local >= '{year_start.to_date_string()}' 
                AND start_date_local < '{now.add(days=1).to_date_string()}'
            """

            yesterday_result = conn.execute(yesterday_query).fetchone()
            month_result = conn.execute(month_query).fetchone()
            year_result = conn.execute(year_query).fetchone()

            conn.close()

            # 构建跑步信息
            running_info_parts = []

            if yesterday_result and yesterday_result[0] > 0:
                running_info_parts.append(
                    f"• 昨天跑步{yesterday_result[0]}次，{yesterday_result[1]}公里"
                )
            else:
                running_info_parts.append("• 昨天未跑步")

            if month_result and month_result[0] > 0:
                running_info_parts.append(
                    f"• 本月跑步{month_result[0]}次，{month_result[1]}公里"
                )
            else:
                running_info_parts.append("• 本月还未跑步")

            if year_result and year_result[0] > 0:
                running_info_parts.append(
                    f"• 今年跑步{year_result[0]}次，{year_result[1]}公里"
                )
            else:
                running_info_parts.append("• 今年还未跑步")

            return "跑步统计：\n" + "\n".join(running_info_parts)

    except Exception as e:
        print(f"Error getting running data: {e}")
        return ""

    return ""


def get_day_of_year():
    """获取今天是今年的第几天"""
    now = pendulum.now(TIMEZONE)
    return now.day_of_year


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


def make_get_up_message(github_token):
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

    day_of_year = get_day_of_year()
    github_activity = get_yesterday_github_activity(github_token)
    running_info = get_running_distance()

    return sentence, is_get_up_early, day_of_year, github_activity, running_info


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

    sentence, is_get_up_early, day_of_year, github_activity, running_info = (
        make_get_up_message(github_token)
    )
    get_up_time = pendulum.now(TIMEZONE).to_datetime_string()

    body = GET_UP_MESSAGE_TEMPLATE.format(
        get_up_time=get_up_time,
        sentence=sentence,
        day_of_year=day_of_year,
        github_activity=github_activity,
        running_info=running_info,
    )

    if is_get_up_early:
        issue.create_comment(body)
        # send to telegram
        if tele_token and tele_chat_id:
            bot = telebot.TeleBot(tele_token)
            try:
                # 使用 markdownify 格式化消息
                formatted_body = markdownify(body)
                bot.send_message(
                    tele_chat_id,
                    formatted_body,
                    parse_mode="MarkdownV2",
                    disable_notification=True,
                )
            except Exception as e:
                print(str(e))
    else:
        print("You wake up late")


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
