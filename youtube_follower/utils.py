import os

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from selenium.common.exceptions import NoSuchElementException


KEY_LOC = os.path.join(os.path.dirname(__file__), '../credentials/api_key.txt')
with open(KEY_LOC, 'r') as f:
    DEVELOPER_KEY = f.read()


YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
    developerKey=DEVELOPER_KEY)

def search(query, max_results=10):
    """
    Searches YouTube and returns the top result 

    INPUT:
        query: (str) search term
        max_results: (int) maximum number of results to return

    OUTPUT:
        top_result: (dict) top search result ID and title

    """

    # Call the search.list method to retrieve results matching the specified
    # query term.
    search_response = youtube.search().list(
      q=query,
      part='id,snippet',
      maxResults=max_results,
      type='video'
    ).execute()
  
    results = {}
  
    # Add each result to the appropriate list, and then display the lists of
    # matching videos, channels, and playlists.
    for search_result in search_response.get('items', []):
        video_id = search_result['id']['videoId'].encode('ascii', 'ignore')
        results[video_id] = search_result['snippet']['title'].encode('ascii', 'ignore')

    return results


def get_metadata_batch(video_ids):
    """
    Helper for get_metadata. Gets metadata for batches of max length of 45
    video_ids

    INPUT:
        video_id: (str)

    OUTPUT:
        result: (dict) video metadata for each video: result[video_id] = {}
    """
    video_ids = ", ".join(video_ids)

    video_response = youtube.videos().list(
        id=video_ids,
        part='snippet, statistics'
        ).execute()

    result = {}

    for video_result in video_response.get('items', []):
        # Get video title, publication date, description, category_id
        snippet = video_result.get('snippet')
        contentDetails = video_result.get('contentDetails')
        statistics = video_result.get('statistics')
        video_id = video_result['id']

        result[video_id] = {'title': snippet.get('title', -1),
                            'date': snippet.get('publishedAt', -1),
                            'description': snippet.get('description', -1),
                            'category_id': snippet.get('categoryId', -1),
                            'channel': snippet.get('channelTitle', -1),
                            'likes': statistics.get('likeCount', -1),
                            'dislikes': statistics.get('dislikeCount', -1),
                            'views': statistics.get('viewCount', -1),
                            'n_comments': statistics.get('commentCount', -1)}

    return result

def get_metadata(video_ids):
    """
    Returns the metadata for the videos in video_ids as a nested dictionary

    INPUT:
        video_ids: (str) list of video_ids

    OUTPUT:
        result: nested dictionary of video_id metadata

    """
    result = {}
    batch_size = 45

    for ix in range(0, len(video_ids), batch_size):
        batch = video_ids[ix: ix + batch_size]
        result.update(get_metadata_batch(batch))

    return result


def get_comments(video_id, max_results=5):
    """
    Gets the top comments for a video_id

    INPUT:
        video_id: (str) 
        max_results: (str) max number of comments to return

    OUTPUT:
        result: (str array) top n comments
    """

    comment_request = youtube.commentThreads().list(
        videoId=video_id,
        maxResults=max_results,
        textFormat='plainText',
        part='snippet',
        order='relevance')

    try:
        comment_response = comment_request.execute()
    except HttpError:
        return -1

    result = []
    for comment_result in comment_response.get('items', []):
        comment = comment_result['snippet']['topLevelComment']
        result.append(comment['snippet']['textOriginal'].encode('ascii', 'ignore'))

    return(result)


class element_does_not_exist(object):
    """
    Selenium expectation for waiting until an object no longer exists

    locator -- used to identify the element
    """
    def __init__(self, locator):
        self.locator = locator

    def __call__(self, driver):
        try:
            element = driver.find_element(*self.locator)
        except NoSuchElementException:
            return True
        return False









