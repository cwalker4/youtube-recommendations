# youtube-recommendations

Scripts for crawling YouTube recommendations and analyzing the results. Main crawler lives in `youtube_follower`. Tested with Python 3.6.4.

## Setup

After cloning into the directory of your choice, there are a couple steps to get everything up and running. First install requirements:

```
pip install -r requirements.txt
```

Run `setup.py`. This simple script does a few things:
1. Creates a `data` folder in your base repository.
2. Creates a SQLite database (`data/crawl.sqlite`) and populates it with required tables.
3. Creates a `credentials` folder and an empty file `credentials/api_key.txt` to hold your YouTube Data API key.

Once you copy your API key into `credentials/api_key.txt` you're ready to go.

## Usage

These scripts aren't optimized for general use (read: not user-friendly), but suppose you wanted a recommendation tree starting from the music video for Pharell's "Happy" where you follow 2 recommendations per video and stop at depth 4. You'd run the following:

```python
from youtube_follower import youtube_follower

happy_id = "ZbZSe6N_BXs"
yf = youtube_follower.YoutubeFollower(
        root_id=happy_id,
        n_splits=2,
        depth=4)
yf.run()
```

Some other features of interest:
* Setting `sample=True` causes the crawler to take a random sample of each video's recommendations after some critical depth `const_depth`. The crawler follows one video in expectation. Useful if you want to run a deeper tree without exponential growth. 
* `youtube_follower.utils.get_top_news_videos()` returns the videos YouTube has featured in a few of its News-related playlists.

## Misc
For efficiency reasons our crawler does not get the recommendations for a video if we have seen it before. This effectively truncates the tree. The implicit assumption is that the recommendations associated with any particular video do not change in the course of the crawl. For certain analyses you might want the full tree: see [this issue](https://github.com/cwalker4/youtube-recommendations/issues/1) and [this script](https://github.com/cwalker4/youtube-recommendations/blob/master/scripts/data_preparation/complete_tree.py) (under development). 


