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

	# Call the search.list method to retrieve results matching the query
	search_response = youtube.search().list(
	  q=query,
	  part='id,snippet',
	  maxResults=max_results,
	  type='video'
	).execute()
  
	video_ids = []
	for search_result in search_response.get('items', []):
		video_ids.append(search_result['id']['videoId'])

	return video_ids


def get_top_news_videos():
    """
    Gets the top news videos from Youtube's 'News', 'World News', and 'National News' channels

    OUTPUT: 
        video_ids: (list) video ids for the videos in YouTube's Top Stories playlists for each channel
    
    """
    playlists = ['PL3ZQ5CpNulQldOL3T8g8k1mgWWysJfE9w', 'PLNjtpXOAJhQLmUEyuWw4hW_6gX8JMJUof', 'PLr1-FC1l_JLFcq9r9Y3uFLkH8G37WmMRQ']
    video_ids = []

    for playlist_id in playlists:
        # get the videos in the Top Stories playlist
        search_response = youtube.playlistItems().list(
            playlistId=playlist_id,
            part='contentDetails',
            maxResults=50
        ).execute()
    
        for search_result in search_response.get('items', []):
            video_id = search_result.get('contentDetails')['videoId']
            if video_id not in video_ids:
                video_ids.append(video_id)

    return video_ids


def video_exists(video_id):
    """
    Check whether root video is still available

    INPUT:
        video_id: (str) video id

    OUTPUT:
        boolean for whether video is available
    """
    query = youtube.videos().list(id=video_id, part='id').execute()
    return query.get('items')


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

        result[video_id] = {'title': snippet.get('title', None),
                            'postdate': snippet.get('publishedAt', None),
                            'description': snippet.get('description', None),
                            'category': snippet.get('categoryId', None),
                            'channel_id': snippet.get('channelId', None),
                            'likes': statistics.get('likeCount', None),
                            'dislikes': statistics.get('dislikeCount', None),
                            'views': statistics.get('viewCount', None),
                            'n_comments': statistics.get('commentCount', None)}

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
        # try getting info in batch
        for _ in range(10):
            try:
                result.update(get_metadata_batch(batch))
                break
            except HttpError:
                pass
        # if can't get in batch, try getting individually 
        else:
            for video_id in batch:
                try:
                    result.update(get_metadata_batch(video_id))
                except HttpError as e:
                    continue
    return result


def get_channel_metadata_batch(channel_ids):
	"""
	Helper for get_channel_metadata. Gets metadata for batches of max length of 45
	video_ids

	INPUT:
		channel_ids: (list of str) channel_ids in a list

	OUTPUT:
		result: (list) nested dict of channel metadata
	"""
	id_str = ",".join(channel_ids)

	response = youtube.channels().list(
		id=id_str,
		part='snippet,statistics,topicDetails'
	).execute()

	result = {}
	for channel_result in response.get('items', []):
		channel_id = channel_result['id']
		statistics = channel_result.get('statistics')
		snippet = channel_result.get('snippet')
		if channel_result.get('topicDetails', []):
			cat_urls = channel_result.get('topicDetails')['topicCategories']
			categories = [url.split('/')[-1] for url in cat_urls]
		else:
			categories = None

		# update the channels dict
		result[channel_id] = {'name': snippet.get('title', None),
							  'country': snippet.get('country', None),
							  'date_created': snippet.get('publishedAt', None),
							  'n_subscribers': statistics.get('subscriberCount'),
							  'n_videos': statistics.get('videoCount', None),
							  'n_views': statistics.get('viewCount', None),
							  'categories': str(categories)}
	return result
	


def get_channel_metadata(channel_ids):
	"""
	Returns the metadata for the channels in channel_ids as a nested list

	INPUT:
		channel_ids: (str) list of channel_ids

	OUTPUT:
		result: nested list of channel_id metadata

	"""
	batch_size = 50  # 50 seems to be the API limit per request
	result = {}
	for ix in range(0, len(channel_ids), batch_size):
		batch = channel_ids[ix: ix+batch_size]
		for _ in range(10):
			try:
				result.update(get_channel_metadata_batch(batch))
				break
			except HttpError:
				pass
		# if can't get in batch, try getting individually 
		else:
			for channel_id in batch:
				try:
					result.update(get_channel_metadata_batch(channel_id))
				except HttpError:
					continue
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


def dict_to_array(dictionary, order):
	"""
	Converts dictionaries in the format 
	{key1: {subkey: vala, key2b: valb},...}
	into a nested list like:
	[[key1, vala, valb], [key2, vala, valb], ...]

	INPUT:
		dict: dictionary to convert
		order: (list) the order in which to populate the list

	OUTPUT:
		output: converted dict

	"""
	res = []
	for key, data in dictionary.items():
		entry = [key]
		entry.extend([data[key] for key in order])
		res.append(entry)
	return res


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









