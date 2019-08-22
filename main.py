# Simple script to run the youtube_follower package
from youtube_follower import youtube_follower
from youtube_follower.utils import get_top_news_videos

root_videos = get_top_news_videos()

for video_id in root_videos:
    yf = youtube_follower.YoutubeFollower(
    		root_id=video_id,
            n_splits=3,
            depth=15,
            const_depth=4,
            sample=True,
            outdir='data/scrape_results')
    yf.run()

