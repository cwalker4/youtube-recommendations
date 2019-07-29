# Simple script to run the youtube_follower package
from youtube_follower import youtube_follower
from youtube_follower.utils import get_top_news_videos

root_videos = get_top_news_videos()

yf = youtube_follower.YoutubeFollower(
    outdir='test'
    )

for video_id in root_videos:
	yf.run(video_id)