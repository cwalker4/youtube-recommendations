# Simple script to re-run previous searches.

import re
import json
import sys
import os

from youtube_follower import youtube_follower

for tree_dir in os.listdir(results_dir):
    tree_path = os.path.join(results_dir, tree_dir)
    if tree_dir in ['video_info.json', 'captions']:
        continue
    query, root_id = scrape_dir.split('_', maxsplit=1)
    
    print("Re-running tree with query {} and root {}".format(query, root_id))
    with open(os.path.join(tree_path, 'params.json')) as f:
        search_params = json.load(f)
    
    yf = youtube_follower.YoutubeFollower(
            query=query,
            n_splits=search_params['n_splits'],
            depth=search_params['depth'],
            outdir='data/scrape_results_redo',
            verbose=False)
    yf.run(root_id)