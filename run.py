import sys
import json
import requests
import timeago
from datetime import datetime
from prettytable import PrettyTable

def get_api_key_from_file(file_path):
    f = open(file_path)
    file_data = json.load(f)
    api_key = str(file_data["key"])
    f.close()
    return api_key

def get_search_parameters(api_key, search_term):
    params = {
            "key": api_key,
            "part": "snippet",
            "type": "video",
            "q": search_term,
            "maxResults": "3"
            }
    return params

def get_videos_parameters(api_key, video_id):
    params = {
            "key": api_key,
            "part": ["snippet", "statistics", "player"],
            "id": video_id
            }
    return params

def get_channel_parameters(api_key, channel_id):
    params = {
            "key": api_key,
            "part": ["snippet", "statistics"],
            "id": channel_id
            }
    return params

def get_request(api_url, params):
    response = requests.get(api_url, params=params)
    json_response = response.json()
    return json_response

def parse_json_search_response_to_dictionary(json_response):
    video_data = {}
    all_videos_list = json_response["items"]
    for video in all_videos_list:
        video_id = video["id"]["videoId"]
        video_title = video["snippet"]["title"]
        channel_id = video["snippet"]["channelId"]
        if (video_id not in video_data):
            video_snippet_data = {"video_title": video_title, "channel_id": channel_id}
            video_data[video_id] = video_snippet_data
    return video_data

def parse_json_videos_response_to_dictionary(video_id, video_ids_dict, json_response):
    snippet = json_response["items"][0]["snippet"]
    video_published_at_datetime = snippet["publishedAt"]
    statistics = json_response["items"][0]["statistics"]
    video_view_count = statistics["viewCount"] 
    video_like_count = statistics["likeCount"]
    video_dislike_count = statistics["dislikeCount"]
    embed_html = json_response["items"][0]["player"]["embedHtml"]
    stats_dictionary = {
            "view_count": video_view_count,
            "like_count": video_like_count,
            "dislike_count": video_dislike_count,
            "published_at": video_published_at_datetime,
            "embed_html": embed_html
            }
    video_data = {}
    video_data[video_id] = stats_dictionary
    video_data[video_id]["title"] = video_ids_dict[video_id]["video_title"]
    video_data[video_id]["channel"] = {"channel_id": video_ids_dict[video_id]["channel_id"]}
    return video_data

def add_channel_data_to_videos_dict(json_response, video_id, video):
    statistics = json_response["items"][0]["statistics"]
    channel_subscriber_count_int = 0
    try:
        channel_subscriber_count_int = int(statistics["subscriberCount"])
    except KeyError:
        channel_subscriber_count_int = -1
    finally:
        snippet = json_response["items"][0]["snippet"]
        channel_title = snippet["title"]
        video[video_id]["channel"]["title"] = channel_title
        channel_view_count = statistics["viewCount"]
        channel_subscriber_count = "{:,}".format(channel_subscriber_count_int)
        channel_video_count = statistics["videoCount"]
        video[video_id]["channel"]["channel_view_count"] = channel_view_count
        video[video_id]["channel"]["channel_subscriber_count"] = channel_subscriber_count
        video[video_id]["channel"]["channel_video_count"] = channel_video_count
    return

def get_video_ids_from_search(api_key, youtube_search_api_url, search_term):
    search_params = get_search_parameters(api_key, search_term)
    json_response = get_request(youtube_search_api_url, search_params)
    video_id_dict = parse_json_search_response_to_dictionary(json_response)
    return video_id_dict

def get_video_metadata_from_ids(api_key, youtube_videos_api_url, video_ids_dict):
    all_videos_metadata = []
    for video_id in video_ids_dict:
        video_params = get_videos_parameters(api_key, video_id)
        json_response = get_request(youtube_videos_api_url, video_params)
        video_data = parse_json_videos_response_to_dictionary(video_id, video_ids_dict, json_response)
        all_videos_metadata.append(video_data)
    return all_videos_metadata

def get_channel_metadata_from_ids(api_key, youtube_channel_api_url, videos):
    all_videos = []
    for video in videos:
        for video_id in video:
            channel_id = video[video_id]["channel"]["channel_id"]
            channel_params = get_channel_parameters(api_key, channel_id)
            json_response = get_request(youtube_channel_api_url, channel_params)
            add_channel_data_to_videos_dict(json_response, video_id, video)
        all_videos.append(video)
    return all_videos

# source: https://chrislovejoy.me/youtube-algorithm/
def calculate_views_to_subscriber_ratio(num_views, num_subs):
    num_views = int(num_views.replace(",",""))
    num_subs = int(num_subs.replace(",",""))
    if (num_subs == 0 or num_subs == -1):
        return 0
    ratio = num_views / num_subs
    return ratio

def custom_score(num_views, ratio):
    num_views = int(num_views)
    ratio = min(ratio, 5)
    score = (num_views * ratio)
    return score

def convert_int_to_comma_sep_string(n):
    return "{:,}".format(n)

def print_table(videos):
    pTable = PrettyTable()
    pTable.field_names = [
            "No.",
            # "Id",
            "Title",
            "Views",
            "Published",
            "Likes/Dislikes %",
            # "Channel Id",
            "Channel Name",
            "Subscribers",
            "Score",
            "View/Sub Ratio"
            ]
    rows = []
    count = 1
    for video in videos:
        for video_id in video:
            like_count = int(video[video_id]["like_count"])
            dislike_count = int(video[video_id]["dislike_count"])
            view_count = int(video[video_id]["view_count"])
            sub_count = int(video[video_id]["channel"]["channel_subscriber_count"].replace(",", ""))
            date_now = datetime.now()
            date = video[video_id]["published_at"]
            datetime_object = datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
            date_ago = timeago.format(datetime_object, date_now, "en")
            views_subscriber_ratio = calculate_views_to_subscriber_ratio(view_count, sub_count)
            score = custom_score(view_count, views_subscriber_ratio)
            try:
                like_dislike_ratio_float = like_count / (like_count + dislike_count)
                like_dislike_ratio = "{:.1%}".format(like_dislike_ratio_float)
            except ZeroDivisionError:
                like_dislike_ratio = video[video_id]["like_count"]
            fields = [
                    count,
                    # "https://www.youtube.com/watch?v=" + video_id,
                    # video_id,
                    video[video_id]["title"],
                    convert_int_to_comma_sep_string(view_count),
                    # video[video_id]["published_at"],
                    date_ago,
                    like_dislike_ratio,
                    # video[video_id]["channel"]["channel_id"],
                    video[video_id]["channel"]["title"],
                    convert_int_to_comma_sep_string(sub_count),
                    score,
                    views_subscriber_ratio
                    ]
        count += 1
        rows.append(fields)
    pTable.add_rows(rows)
    print(pTable)

def add_score_to_videos(videos):
    date_now = datetime.now()
    for video in videos:
        for video_id in video:
           date = video[video_id]["published_at"]
           datetime_object = datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
           date_ago = timeago.format(datetime_object, date_now, "en")
           views_subscriber_ratio = calculate_views_to_subscriber_ratio(video[video_id]["view_count"], video[video_id]["channel"]["channel_subscriber_count"])
           score = custom_score(video[video_id]["view_count"], views_subscriber_ratio)
           like_count = int(video[video_id]["like_count"])
           dislike_count = int(video[video_id]["dislike_count"])
           try:
               like_dislike_ratio_float = like_count / (like_count + dislike_count)
               like_dislike_ratio = "{:.1%}".format(like_dislike_ratio_float)
           except ZeroDivisionError:
               like_dislike_ratio = video[video_id]["like_count"]
           video[video_id]["date_ago"] = date_ago
           video[video_id]["view_sub_ratio"] = views_subscriber_ratio
           video[video_id]["score"] = score
           video[video_id]["like_dislike_ratio"] = like_dislike_ratio
    return videos
           


def output_data_to_file(search_term):
    credentials_file_path = "./credentials.json"
    youtube_search_api_url = "https://www.googleapis.com/youtube/v3/search"
    youtube_videos_api_url = "https://www.googleapis.com/youtube/v3/videos"
    youtube_channel_api_url = "https://www.googleapis.com/youtube/v3/channels"

    api_key = get_api_key_from_file(credentials_file_path)

    # get video ids
    video_ids_dict = get_video_ids_from_search(api_key, youtube_search_api_url, search_term)
    # get video metadata and create videos dictionary
    videos = get_video_metadata_from_ids(api_key, youtube_videos_api_url, video_ids_dict)
    # get channel metadata and add to videos dictionary 
    videos = get_channel_metadata_from_ids(api_key, youtube_channel_api_url, videos)

    videos = add_score_to_videos(videos)

    with open("data.json", "w") as fp:
        json.dump(videos, fp)

if __name__ == "__main__":
    output_data_to_file()
    # credentials_file_path = "./credentials.json"
    # youtube_search_api_url = "https://www.googleapis.com/youtube/v3/search"
    # youtube_videos_api_url = "https://www.googleapis.com/youtube/v3/videos"
    # youtube_channel_api_url = "https://www.googleapis.com/youtube/v3/channels"

    # search_term = str(sys.argv[1])

    # api_key = get_api_key_from_file(credentials_file_path)

    # # get video ids
    # video_ids_dict = get_video_ids_from_search(api_key, youtube_search_api_url, search_term)
    # # get video metadata and create videos dictionary
    # videos = get_video_metadata_from_ids(api_key, youtube_videos_api_url, video_ids_dict)
    # # get channel metadata and add to videos dictionary 
    # videos = get_channel_metadata_from_ids(api_key, youtube_channel_api_url, videos)

    # print table
    # print_table(videos)
